import zmq
import zmq.auth

# This is just to demonstrate that without security, zmq is insecure.
# As a demonstration:
#     1. Open wireshark and listen on interface 'lo0'
#     2. Start this server
#     3. Run the insecure_zmq_client
#     4. View data packets in wireshark, paying attention to the data packet 
#        containing 'Hello, World'. Wow. Such insecure. 

context = zmq.Context(1)

sock = context.socket(zmq.PULL)
sock.bind('tcp://127.0.0.1:12345')
msg = sock.recv()
print msg
