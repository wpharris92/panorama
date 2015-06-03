import zmq.auth as auth
import ssl
from threading import Thread
import cmd
from panorama import PanoramaClient

DEFAULT_MATCH_PERCENT = .5
DEFAULT_NUM_REPLIES = 5

class ClientOptions(cmd.Cmd):
   def __init__(self, client):
      cmd.Cmd.__init__(self)
      self.client = client

   prompt = '>> '

   def do_request(self, line):
      args = line.split(' ')
      if not len(args):
         print 'Must make request for url'
      url = args[0]
      num_replies = DEFAULT_NUM_REPLIES
      if len(args) > 1:
         num_replies = int(args[1])
      min_match_percent = DEFAULT_MATCH_PERCENT
      if len(args) > 2:
         min_match_percent = float(args[2])

      try:
         i_saw, they_saw = self.client.request(url, num_replies=num_replies)
      except Exception as ex:
         print 'Failed to make request for %s: %r' % (url, ex)
         return False

      print 'From this client, saw %r' % i_saw
      print 'Other clients saw %r' % they_saw

      percent_match = 0
      if i_saw in they_saw:
         percent_match = float(they_saw[i_saw]) / sum(they_saw.values())

      if percent_match >= min_match_percent:
         print 'I WOULD trust this connection'
      else:
         print 'I would NOT trust this connection'

   def do_stop(self, line):
      self.client.stop()

   def do_start(self, line):
      self.client.start()

   def do_EOF(self, line):
      return True

if __name__ == '__main__':
   client = PanoramaClient('tcp://127.0.0.1:12345',
      auth.load_certificate('server.key')[0],
      'client')
   client.start()

   ClientOptions(client).cmdloop()
