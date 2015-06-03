import zmq.auth as auth
from time import sleep
from common import Reply
from traceback import print_exc
from panorama import PanoramaClient

# Potential names:
#  Panorama
#  Peerspectives (lol)
#  Periphrials
DEFAULT_NUM_REPLIES = 5
DEFAULT_TIMEOUT = 5

STATE_READY = 'READY'
STATE_RUNNING = 'RUNNING'
STATE_STOPPED = 'STOPPED'

class EvilPanoramaClient(PanoramaClient):

   def reply_to_requests(self, request_queue, reply_socket):
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
            # EVIL CLIENT SENDS BAD CERTIFICATE INFO
            reply.reply = 'BAD_CERTIFICATE_INFO'
         except:
            print 'Failed to get server certificate:'
            print_exc()
            continue

         reply_socket.send_multipart(reply.to_message())

try:
   clients = []
   for _ in range(10):
      client = EvilPanoramaClient('tcp://127.0.0.1:12345',
         auth.load_certificate('server.key')[0],
         'client')
      client.start()
      clients.append(client)
   while True:
      # Just stick around to reply to requests
      sleep(1)
except:
   print_exc()
   for client in clients:
      client.stop
