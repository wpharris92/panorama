import zmq.auth
import json
import hashlib
import ssl

# Format: [HELLO_MSG]
HELLO_MSG = 'HELLO'

# Format: [PING]
PING = 'PING'

# Format: [GOODBYE_MSG]
GOODBYE_MSG = 'GOODBYE'

# Format: [REQUEST_MSG, <url>, <num_replies>, <request id>, <this_view>]
REQUEST_MSG = 'REQUEST'

# Format: [REPLY_MSG, <url>, <request id>, <reply>]
# When receiving replys, request id will be dropped. It should be echoed back by
# clients so that the server can route the reply to the correct location
REPLY_MSG = 'REPLY'

SSL_PORT = 443

def hash_of(certificate):
   return hashlib.sha256(certificate).hexdigest()

def get_server_data(url):
   addr = (url, SSL_PORT)
   return hash_of(ssl.get_server_certificate(addr))

def get_keys(cert_prefix):
   try:
      return zmq.auth.load_certificate(cert_prefix + '.key_secret')
   except:
      files = zmq.auth.create_certificates('.', cert_prefix)
      for f in files:
         if 'secret' in f:
            return zmq.auth.load_certificate(f)

def create_socket(context, sock_type, secret_key, public_key, server_key=None, socket_id=None):
   socket = context.socket(sock_type)

   if sock_type == zmq.ROUTER:
      socket.router_mandatory = 1

   socket.curve_secretkey = secret_key
   socket.curve_publickey = public_key
   # If server_key is given, assume client. No server key -> I'm the server
   if server_key:
      socket.curve_serverkey = server_key
      if socket_id:
         socket.setsockopt_string(zmq.IDENTITY, socket_id)
   else:
      socket.curve_server = True
   return socket

class Request:
   def __init__(self, url, this_view, num_replies=None, request_id=None):
      assert url, 'Url not given'
      assert num_replies or request_id and not (num_replies and request_id), 'request_id xor num_replies must be given'

      self.url = url
      self.request_id = request_id
      self.num_replies = num_replies
      self.this_view = this_view

   @classmethod
   def from_message(cls, message):
      assert message, 'Message was None'
      assert len(message) > 0, 'Message had 0 length'
      assert message[0] == REQUEST_MSG, 'Message was not of type REQUEST instead was %s' % message[0]
      assert len(message) >= 5, 'Malformed message: %r' % message

      return cls(message[1],
         message[4] if len(message[4]) else None,
         int(message[2]) if len(message[2]) else None,
         message[3])

   def to_message(self):
      return [REQUEST_MSG,
         self.url,
         str(self.num_replies) if self.num_replies else '',
         str(self.request_id) if self.request_id else '',
         str(self.this_view) if self.this_view else '']

class Reply:
   def __init__(self, request_id, url, reply):
      assert url, 'Url not given'

      self.url = url
      self.request_id = request_id
      self.reply = reply

   @classmethod
   def from_message(cls, message):
      assert message, 'Message was None'
      assert len(message) > 0, 'Message had 0 length'
      assert message[0] == REPLY_MSG, 'Message was not of type REPLY instead was %s' % message[0]
      assert len(message) >= 3, 'Malformed message: %r' % message

      url = message[1]
      if len(message) > 3:
         # The reply has a request id
         request_id = message[2]
         reply = message[3]
      else:
         request_id = None
         reply = message[2]

      return cls(request_id, url, reply)

   # Used by clients to easily turn Requests to Replys
   @staticmethod
   def from_request(request):
      assert request.request_id, 'from_request should be used on requests with request_ids'
      return Reply(request.request_id, request.url, None)

   @staticmethod
   def from_request_msg(request_msg):
      return Reply.from_request(Request.from_message(request_msg))

   def to_message(self):
      message = [REPLY_MSG, str(self.url)]
      if self.request_id:
         message.append(str(self.request_id))
      message.append(str(self.reply))
      return message



















