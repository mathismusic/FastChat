# echo-client.py

import socket
import json

HOST = "192.168.103.215"  # The server's hostname or IP address
PORT = 61002  # The port used by the server

class Message:
    def __init__(self, sender, rec, msg) -> None:
        self.sender =  sender
        self.recipient = rec
        self.message = msg
    
    def __repr__(self) -> str:
        return json.dumps({"Sender": self.sender, "Recipient": self.recipient, "Message": self.message})

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((HOST, PORT))
    a=""
    username = input("Username: ")
    password = input("Password: ")
    login_data = {"Username" : username , "Password" : password}
    s.sendall(bytes(json.dumps(login_data).encode()))

    data = s.recv(1024).decode()
    while(data == "invalid"):
        username = input("Username: ")
        password = input("Password: ")
        login_data = {"Username" : username , "Password" : password}
        s.sendall(bytes(json.dumps(login_data).encode()))

        data = s.recv(1024).decode()
    
    print(data)

    while(a!="exit"): 

        rec = input("To: ")
        message = input("Message: ")

        s.sendall(bytes(str(Message(username,rec,message)).encode()))
        data = s.recv(1024).decode()
        if data != "Received.": print("Received:", data)
        else: print("Message sent successfully.") # tick.

