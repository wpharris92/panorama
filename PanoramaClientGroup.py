import zmq.auth as auth
from time import sleep
from traceback import print_exc
from panorama import PanoramaClient

if __name__ == '__main__':
   try:
      clients = []
      for _ in range(10):
         client = PanoramaClient('tcp://127.0.0.1:12345',
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
