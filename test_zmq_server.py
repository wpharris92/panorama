import zmq
import common
import zmq.auth
from zmq.auth.thread import ThreadAuthenticator
import ssl
from traceback import print_exc
from random import SystemRandom

print 'zmq version =', zmq.zmq_version()

active_clients = set()
active_requests = {}
rand = SystemRandom()

def handle_message(message):
   # First element is ID of client
   client_id = message[0]
   message = message[1]

   return len(active_clients)

def run_server():
   pub, sec = common.get_keys('server')
   
   socket = common.create_socket(context, 
      zmq.ROUTER,
      sec,
      pub);

   socket.bind('tcp://127.0.0.1:12345')

   try:
      active = True
      while active:
         message = socket.recv_multipart()
         client_id = message[0]
         msg_type = message[1]
         # WELCOME begets HELLO
         if msg_type == common.HELLO_MSG:
            if client_id not in active_clients:
               active_clients.add(client_id)
            socket.send_multipart([
               client_id,
               common.WELCOME_MSG])

         elif msg_type == common.REPLY_MSG:
            print 'Got reply for', message[2]
            if len(message) < 5:
               continue
            url = message[2]
            request_id = message[3]
            reply = message[4]
            if request_id not in active_requests:
               continue
            request_info = active_requests[request_id]
            request_info[1].append(reply)
            # Temporary
            if len(request_info[1]) >= 9:
               response = [request_info[0],
               common.REPLY_MSG,
               url]
               response.extend(request_info[1])

               socket.send_multipart(response)
               del active_requests[request_id]

         elif msg_type == common.REQUEST_MSG:
            print 'Got request for', message[2]
            request_id = None
            while not request_id or request_id in active_requests:
               request_id = hex(rand.getrandbits(128))
            active_requests[request_id] = [client_id, []]
            for client in active_clients:
               if client != client_id:
                  socket.send_multipart([
                     client,
                     common.REQUEST_MSG,
                     message[2],
                     request_id])

         elif msg_type == common.GOODBYE_MSG:
            print 'Client id', client_id, 'is leaving'
            active_clients.discard(client_id)

         else:
            print 'Got unknown message type:', message[1]

         # For now, we're active as long as folks are connected
         active = len(active_clients)
   except:
      print_exc()
      pass

context = zmq.Context.instance()

auth = ThreadAuthenticator(context)
auth.start()
auth.configure_curve(domain='*', location=zmq.auth.CURVE_ALLOW_ANY)

try:
   run_server()
except:
   print_exc()
finally:
   auth.stop()
