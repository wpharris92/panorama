import zmq
import common
from common import Request, Reply
import zmq.auth
from zmq.auth.thread import ThreadAuthenticator
import ssl
from traceback import print_exc
from random import SystemRandom
from time import time, sleep
import threading
from threading import Thread
from base64 import b64encode, b64decode

import peewee
from peewee import *

MYSQL_USER = 'WillHarris'
MYSQL_DATABASE = 'test'

SECONDS_BEFORE_PING = 5
SECONDS_BEFORE_DISCONNECT = 15
PING_FREQUENCY = 5 # Ping every 5 seconds

DEFAULT_WINDOW_MINS = .5 # 60 * 7 # 1 week

active_clients = {}
active_requests = {}
rand = SystemRandom()

socket_lock = threading.Lock()

class ClientInfo:
   def __init__(self, client_id):
      self.id = client_id
      # replies_requested is a map (request_id -> number remaining), to support concurrent requests
      self.replies_requested = {} 
      # last_action_time, so we can check if a client is still connected
      self.last_action_time = time()

   def client_action(self):
      self.last_action_time = time()

   def add_request(self, request_id, num_replies_requested):
      self.replies_requested[request_id] = num_replies_requested
      active_requests[request_id] = self

def load_database(database_name, user, password=None):
   return MySQLDatabase(database_name, user=user, password=password)

def save_request(client_id, request):
   save_access(client_id, request.url, request.this_view)

def save_reply(client_id, reply):
   save_access(client_id, reply.url, reply.reply)

def save_access(client_id, url, cert_data):
   access = Access(
      client_id=client_id,
      url=url,
      cert_hash=cert_data,
      access_time=time())
   try:
      access.save()
   except peewee.IntegrityError:
      print 'Updating existing database entry'
      access = Access.get(Access.client_id == client_id,
         Access.url == url)
      access.cert_hash = cert_data
      access.access_time = time()
      access.save()

def access_to_reply(access):
   return Reply('',
      access.url,
      access.cert_hash)

def load_accesses(client_id, url, window=DEFAULT_WINDOW_MINS):
   return Access.select().where(
      Access.client_id != client_id,
      Access.url == url,
      Access.access_time > time() - (DEFAULT_WINDOW_MINS * 60))

def get_database_replies(client_id, url, window=DEFAULT_WINDOW_MINS):
   accesses = load_accesses(client_id, url, window)
   return [(access.client_id, access_to_reply(access)) for access in accesses]

# Iterate through the clients and check how long it's been since they were active.
# If it's been longer than SECONDS_BEFORE_PING, ping them.
# If it's been longer than SECONDS_BEFORE_DISCONNECT, disconnect them.
def run_heartbeats(socket, client_map):
   while True:
      print 'There are %d clients connected' % len(client_map)
      # Copy client_set so we're not iterating over it directly (threading issues)
      for client in set(client_map.values()):
         if time() - client.last_action_time > SECONDS_BEFORE_DISCONNECT:
            print 'Disconnecting', client.id
            try:
               with socket_lock:
                  socket.send_multipart([client.id, common.GOODBYE_MSG])
            except:
               # Client isn't there! Don't do anything special.
               print_exc()
               pass
            # Disconnect client
            for request in client.replies_requested:
               if request in active_requests:
                  del active_requests[request]
            if client.id in client_map:
               del client_map[client.id]

         elif time() - client.last_action_time > SECONDS_BEFORE_PING:
            # Ping the client
            try:
               with socket_lock:
                  socket.send_multipart([b64decode(client.id), common.PING])
            except:
               # Couldn't talk to the client. We'll try again later
               print_exc()
               pass
      sleep(PING_FREQUENCY)

def run_server():

   # Prepare the database
   Access.create_table(fail_silently=True)

   # Set up the ZMQ socket
   pub, sec = common.get_keys('server')
   
   socket = common.create_socket(zmq.Context.instance(), 
      zmq.ROUTER,
      sec,
      pub);

   socket.bind('tcp://127.0.0.1:12345')

   poller = zmq.Poller()
   poller.register(socket, zmq.POLLIN)

   # Start the heartbeat thread
   heartbeat_thread = Thread(target=run_heartbeats, args=(socket, active_clients))
   heartbeat_thread.daemon = True
   heartbeat_thread.start()

   try:
      active = True
      while active:
         if (poller.poll()):
            pass
         # Now there should be a message ready
         with socket_lock:
            message = socket.recv_multipart()
         client_id = b64encode(message[0])
         msg_type = message[1]

         if msg_type == common.HELLO_MSG:
            if client_id not in active_clients:
               active_clients[client_id] = ClientInfo(client_id)

         elif msg_type == common.REPLY_MSG:
            reply = Reply.from_message(message[1:])
            if reply.request_id not in active_requests:
               continue

            save_reply(client_id, reply)

            request_info = active_requests[reply.request_id]

            reply.request_id = None # Don't need when replying to client

            with socket_lock:
               socket.send_multipart([b64decode(request_info[0])] + reply.to_message())

            request_info[1] -= 1
            if not request_info[1]:
               # We've sent all the requested responses
               del active_requests[request_id]

         elif msg_type == common.REQUEST_MSG:
            request_id = None
            while not request_id or request_id in active_requests:
               request_id = hex(rand.getrandbits(128))

            forwarded_request = Request.from_message(message[1:])
            forwarded_request.request_id = request_id

            save_request(client_id, forwarded_request)

            num_replies_requested = forwarded_request.num_replies

            active_requests[request_id] = [client_id, forwarded_request.num_replies]
            forwarded_request.num_replies = '' # Clear since we're sending to other clients

            do_not_ask = set((client_id,))
            # Return replies from the database
            for client_asked, reply in get_database_replies(client_id, forwarded_request.url):
               print 'Sending reply from database'
               do_not_ask.add(client_asked)
               with socket_lock:
                  socket.send_multipart([b64decode(client_id)] + reply.to_message())
               num_replies_requested -= 1

            num_requests_sent = 0
            for client in active_clients.values():
               if num_requests_sent >= num_replies_requested:
                  break

               if client.id not in do_not_ask:
                  do_not_ask.add(client.id)
                  message_to_send = [b64decode(client.id)]
                  message_to_send.extend(forwarded_request.to_message())
                  try:
                     print 'Making request to another client'
                     with socket_lock:
                        socket.send_multipart(message_to_send)
                  except:
                     print_exc()
                     continue
                  num_requests_sent += 1

         elif msg_type == common.GOODBYE_MSG:
            print 'Client id', client_id, 'is leaving'
            if client_id in active_clients:
               del active_clients[client_id]
            # Don't update last action time
            continue

         elif msg_type == common.PING:
            # Don't do anything, last action time will be updated
            pass

         else:
            print 'Got unknown message type:', message[1]

         active_clients[client_id].last_action_time = time()
   except:
      print_exc()
      pass

auth = ThreadAuthenticator(zmq.Context.instance())
auth.start()
auth.configure_curve(domain='*', location=zmq.auth.CURVE_ALLOW_ANY)

database_name = MYSQL_DATABASE
username = MYSQL_USER

db = load_database(database_name, username)

# Ew ew ew I don't know how to define these before having an instance of the database, 
# So for now their definitions live here
class Access(Model):
   client_id = peewee.CharField()
   url = peewee.CharField()
   cert_hash = peewee.CharField()
   access_time = peewee.IntegerField()

   class Meta:
      database = db
      # Set up unique constraints
      indexes = (
         # Each client may have one entry per url
         (('client_id', 'url'), True),
      )

try:
   run_server()
except:
   print_exc()
finally:
   auth.stop()
