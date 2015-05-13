import zmq
import common
import zmq.auth as auth
import ssl
import OpenSSL
import json
from threading import Thread
from time import sleep
import random
from traceback import print_exc
import hashlib

# Potential names:
#  Panorama
#  Peerspectives (lol)
#  Periphrials
class RequestHandler(Thread):
   def __init__(self, request_address, reply_socket):
      super(RequestHandler, self).__init__()

      # Connect to request_address for messages
      self.request_socket = zmq.Context.instance().socket(zmq.PULL)
      self.request_socket.connect(request_address)

      self.reply_socket = reply_socket

   def run(self):
      self.active = True

      while self.active:
         if self.request_socket.poll(timeout=100):
            req = self.request_socket.recv_multipart()
            print req
            if len(req) < 2:
               continue
            url = req[0]
            request_id = req[1]

            addr = (url, 443)
            cert = ssl.get_server_certificate(addr)

            print [
               common.REPLY_MSG,
               url,
               request_id]
            self.reply_socket.send_multipart([
               common.REPLY_MSG,
               url,
               request_id,
               str(cert)])

class PanoramaClient(Thread):
   def __init__(self, server_address, server_key, client_cert_prefix, identity=None):
      super(PanoramaClient, self).__init__()
      self.context = zmq.Context.instance()

      # Load client private & public keys
      pub, sec = common.get_keys(client_cert_prefix)

      # Set up socket and connect to server
      self.socket = common.create_socket(self.context,
         zmq.DEALER,
         sec,
         pub,
         server_key,
         unicode(identity) if identity else None);
      self.socket.connect(server_address)

      client_id = str(random.randrange(1000000))
      # Set up method for server to request from client
      req_address = 'inproc://requests_' + client_id
      self.req_socket = self.context.socket(zmq.PUSH)
      self.req_socket.bind(req_address)
      self.req_handler = RequestHandler(req_address, self.socket)

      # Set up socket to push replies from server
      rep_address = 'inproc://replies_' + client_id
      self.rep_socket = self.context.socket(zmq.PUB)
      self.rep_socket.bind(rep_address)

      # Set up request map
      self.requests = {}

      # Set state
      self.state = 'READY'

   def run(self):
      self.state = 'RUNNING'

      self.req_handler.active = True
      self.req_handler.start()

      # Say hello to the server
      self.socket.send_string(common.HELLO_MSG)
      # Get reply. Server must WELCOME
      welcome = self.socket.recv_string()
      if welcome != common.WELCOME_MSG:
         self.state = 'SHUT_DOWN'
         raise RuntimeError('Server did not send WELCOME, instead sent: %s' % welcome)

      # Main loop, send requests, get replies
      while self.state == 'RUNNING':
         sleep(random.random())
         # Check for requests that need to be sent
         if (len(self.requests)):
            for req in list(self.requests):
               print req
               self.socket.send_multipart([
                  common.REQUEST_MSG,
                  req])
               del self.requests[req]

         # Check the incoming mail
         if self.socket.poll(100):
            msg = self.socket.recv_multipart()
            msg_type = msg[0]
            # First frame is message type
            if msg_type == common.REQUEST_MSG:
               # Second frame of request is url
               self.req_socket.send_multipart(msg[1:])
            elif msg_type == common.REPLY_MSG:
               for thing in msg:
                  print thing[:20],
               print 
               # Second (and on) frames of reply are MAC(hash(cert))
            else:
               print 'Got unknown message type:', msg_type

      self.state = 'SHUT_DOWN'

   def shutdown(self):
      if self.state == 'READY':
         raise RuntimeError("Can't shutdown client before starting it!")
      self.state = 'SHUTTING_DOWN'
      self.req_handler.active = False
      while self.state == 'SHUTTING_DOWN':
         print 'waiting for shutdown...', self.state
         sleep(.5)
      self.socket.send_string(common.GOODBYE_MSG)

   def request(self, url):
      self.requests[url] = None

try:
   clients = []
   for _ in range(10):
      client = PanoramaClient('tcp://127.0.0.1:12345',
         auth.load_certificate('server.key')[0],
         'client')
      client.start()
      clients.append(client)
   clients[0].request('www.google.com')
   sleep(5)
   for client in clients:
      client.shutdown()
except:
   print_exc()
   client.shutdown()

exit()

addr = ('www.google.com', 443)
cert = ssl.get_server_certificate(addr)
print cert
x509 = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_PEM, cert)
print x509.get_subject().get_components()
