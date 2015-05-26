import zmq
import common
from common import Request, Reply
import zmq.auth as auth
import ssl
import OpenSSL
import json
from threading import Thread
from time import sleep, time
import random
from traceback import print_exc
import hashlib
import inspect
from Queue import Queue, Empty, Full
from multiprocessing.pool import ThreadPool
import json

# Potential names:
#  Panorama
#  Peerspectives (lol)
#  Periphrials
DEFAULT_NUM_REPLIES = 5
DEFAULT_TIMEOUT = 5

STATE_READY = 'READY'
STATE_RUNNING = 'RUNNING'
STATE_STOPPED = 'STOPPED'

def reply_to_requests(request_queue, reply_socket):
   while True:
      request_msg = request_queue.get(block=True)
      try:
         reply = Reply.from_request_msg(request_msg)
      except:
         # Invalid request
         print_exc()
         continue

      print 'Got request for url:', reply.url
      try:
         reply.reply = common.get_server_data(reply.url)
      except:
         print 'Failed to get server certificate:'
         print_exc()
         continue

      reply_socket.send_multipart(reply.to_message())

def delegate_messages(client, incoming_socket, request_queue, reply_listeners):
   while True:
      msg = incoming_socket.recv_multipart()
      # First frame is message type
      msg_type = msg[0]

      if msg_type == common.REQUEST_MSG:
         # Pass to the request queue
         request_queue.put(msg, block=True, timeout=.25)

      elif msg_type == common.REPLY_MSG:
         print 'Got reply for', msg[1]
         # Publish the reply
         client.publish_reply(msg)

      elif msg_type == common.GOODBYE_MSG:
         print 'Disconnected by server'
         client.stop()

      elif msg_type == common.PING:
         # Don't delegate, just reply here
         incoming_socket.send_multipart([common.PING])

      else:
         print 'Got unknown message type: %s, ignoring it' % msg_type

class PanoramaClient():
   def __init__(self, server_address, server_key, client_cert_prefix):
      self.context = zmq.Context.instance()

      # Load client private & public keys
      pub, sec = common.get_keys(client_cert_prefix)

      # Set up socket and connect to server
      self.server_socket = common.create_socket(self.context,
         zmq.DEALER,
         sec,
         pub,
         server_key);
      self.server_socket.connect(server_address)

      # Set up queue to push requests to
      request_queue = Queue()

      # List of reply listeners
      self.reply_listeners = []

      # Set up thread to delegate messages
      message_delegate = Thread(target=delegate_messages, args=(self, self.server_socket, request_queue, self.reply_listeners))
      message_delegate.daemon = True
      message_delegate.start()

      # Set up thread to handle requests
      request_handler = Thread(target=reply_to_requests, args=(request_queue, self.server_socket))
      request_handler.daemon = True
      request_handler.start()

      self.state = STATE_READY

   def start(self):
      self.server_socket.send_multipart([common.HELLO_MSG])
      self.state = STATE_RUNNING

   def stop(self):
      self.server_socket.send_multipart([common.GOODBYE_MSG])
      self.state = STATE_STOPPED

   def publish_reply(self, message):
      for reply_listener in self.reply_listeners:
         try:
            reply_listener.put(message, block=True, timeout=.25)
         except Full:
            print 'Queue was full'
            pass

   def get_reply_listeners(self):
      return self.reply_listeners

   def get_reply_listener(self):
      listener = Queue()
      self.get_reply_listeners().append(listener)
      return listener

   def del_reply_listener(self, listener):
      self.reply_listeners.remove(listener)

   # Timeout is in seconds
   def request(self, url, timeout=DEFAULT_TIMEOUT, num_replies=DEFAULT_NUM_REPLIES):
      assert self.state == STATE_RUNNING, 'Must make requests on running client'

      reply_listener = self.get_reply_listener()

      # Try to get the certificate to send to the server to be added to the database
      # Also, some good error checking so we're not sending requests for bogus urls
      this_view = common.get_server_data(url)

      request = Request(
         url,
         this_view,
         num_replies=num_replies)

      # Send the request
      self.server_socket.send_multipart(request.to_message())

      start = time()
      replies = []
      while len(replies) < DEFAULT_NUM_REPLIES:
         if time() - start >= timeout:
            break

         try:
            reply_msg = reply_listener.get(block=True, timeout=.1)
         except Empty:
            continue

         try:
            rep = Reply.from_message(reply_msg)
         except:
            # Malformed reply
            print_exc()
            continue

         if rep.url == url:
            replies.append(rep.reply)

      self.del_reply_listener(reply_listener)

      return replies

try:
   clients = []
   for _ in range(10):
      client = PanoramaClient('tcp://127.0.0.1:12345',
         auth.load_certificate('server.key')[0],
         'client')
      client.start()
      clients.append(client)

   sleep(3)
   print clients[0].request('www.google.com')

   for client in clients:
      if client.state == STATE_RUNNING:
         sleep(2)
         client.stop()
   # replies = clients[0].request('www.google.com')
   # print len(replies)
except:
   print_exc()
