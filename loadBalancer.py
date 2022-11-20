import socket
import json
import sys
from server import Server

# load balancer server
class LoadBalancer:
    def __init__(self, *servers, algorithm='least-load') -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.HOST = "192.168.103.215"  # The server's hostname or IP address
        self.PORT = 61001 if len(sys.argv) == 1 else 61002  # The port used by the server
        self.servers = list(servers)
        self.algorithm = algorithm


    
    def accept_client(self):
        pass

    def choose_server(self):
        pass

    def 