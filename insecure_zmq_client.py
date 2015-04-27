import zmq
import zmq.auth

# Used as insecure zmq demonstration. See insecure_zmq_server.py for demo steps

context = zmq.Context(1)

sock = context.socket(zmq.PUSH)
sock.connect('tcp://localhost:12345')
sock.send('Hello, World')
