# echo-client.py

import socket

HOST = "192.168.103.215"  # The server's hostname or IP address
PORT = 5001  # The port used by the server

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((HOST, PORT))
    a=""
    while(a!="exit"):
        a = input("Client: ")
        s.sendall(bytes(str(a).encode()))
        data = s.recv(1024).decode()
        if data != "Received.": print("Received:", data)

