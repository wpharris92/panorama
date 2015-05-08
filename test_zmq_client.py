import zmq
import common
import zmq.auth as auth
import ssl
import OpenSSL
import json
from threading import Thread

# Potential names:
#  Panorama
#  Peerspectives (lol)
#  Periphrials
class RequestHandler(Thread):
   def __init__(self, request_address, reply_socket):
      super(RequestHandler, self).__init__()
      print 'Ya sure did call __init__'
      # Connect to request_address for messages
      self.request_socket = zmq.Context.instance().socket(zmq.PULL)
      self.request_socket.connect(request_address)

      self.reply_socket = reply_socket
      self.active = True

   def run(self):
      countdown = 100
      while self.active and countdown > 0:
         countdown -= 1
         message = self.request_socket.poll(timeout=100)
         print message,

   def set_active(self, value):
      self.active = value

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
         unicode(identity));
      self.socket.connect(server_address)

      # Set up method for server to request from client
      req_address = 'inproc://requests'
      self.req_socket = self.context.socket(zmq.PUSH)
      self.req_socket.bind(req_address)
      self.req_handler = RequestHandler(req_address, self.socket)

      self.req_handler.start()

   def run(self):
      # Say hello to the server
      self.socket.send_string(common.HELLO_MSG)
      # Get reply. Server must WELCOME
      reply = self.socket.recv()
      assert(reply == common.WELCOME_MSG)
      print reply

   def shutdown(self):
      self.req_handler.set_active(False)

try:
   client = PanoramaClient('tcp://127.0.0.1:12345',
      auth.load_certificate('server.key')[0],
      'client',
      'WillRocks')
   client.start()
except:
   client.shutdown()

exit()
pub, sec = common.get_keys('client')

socket = common.create_socket(context,
   zmq.DEALER,
   sec,
   pub,
   auth.load_certificate('server.key')[0],
   u'OH_HAI');

connect_to_server(socket, 'tcp://127.0.0.1:12345')

addr = ('www.google.com', 443)
cert = ssl.get_server_certificate(addr)
print cert
x509 = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_PEM, cert)
print x509.get_subject().get_components()
# socket.send_json(addr)
