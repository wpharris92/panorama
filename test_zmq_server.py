import zmq
import common
import zmq.auth
from zmq.auth.thread import ThreadAuthenticator
import ssl
from traceback import print_exc

print 'zmq version =', zmq.zmq_version()

# client ID -> socket (to reply on)
active_clients = {}


def handle_message(message):
   # First element is ID of client
   client_id = message[0]
   print 'ID is: ' + client_id
   message = message[1:]
   for req in message:
      print req

def run_server():
   pub, sec = common.get_keys('server')
   
   socket = common.create_socket(context, 
      zmq.ROUTER,
      sec,
      pub);

   socket.bind('tcp://127.0.0.1:12345')

   message = None
   try:
      message = socket.recv_multipart()
      print message
      handle_message(message)
      message[1] = 'Welcome'
      socket.send_multipart(message)
   except Exception as e:
      print e
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
