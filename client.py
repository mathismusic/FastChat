# echo-client.py

import socket
import json
import sys
from select import select

HOST = "192.168.43.215"  # The server's hostname or IP address
PORT = 61002  # The port used by the server

class Message:
    def __init__(self, sender, rec, msg) -> None:
        self.sender =  sender
        self.recipient = rec
        self.message = msg
    
    def __repr__(self) -> str:
        return json.dumps({"Sender": self.sender, "Recipient": self.recipient, "Message": self.message})

class Client:
    def __init__(self) -> None:
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # the client's socket
        self.HOST = "192.168.43.215"  # The server's hostname or IP address
        self.PORT = 61002  # The port used by the server
        self.username = None
        self.receiver = None # who is the client talking to. make receiver a class for dms and groups.
        # add fields to remember username and password to auto-login next time. (use a local client-specific database/file to store local client stuff)
        
    def login(self) -> None:
        self.s.connect((self.HOST, self.PORT)) # go to port self.PORT on machine self.HOST
        try:
            while(True):
                username = input("Username (type -1 to create an account): ")
                newuser = (username == '-1')
                if newuser:
                    username = input("Choose username: ")
                password = input(("Choose " if newuser else "") + "Password: ")
                login_data = {"Username" : username, "Password" : password, "Newuser" : newuser}
                self.s.sendall(json.dumps(login_data).encode())
                data = self.s.recv(1024).decode()
                if (data == "invalid"):
                    print("This username already exists. Please try again." if newuser else "Invalid username, please try again.")
                else: break
        except KeyboardInterrupt:
            print("Caught keyboard interrupt, exiting")

        self.username = username

    def sendMessage(self):
        # recipient = input("Continue conversation with: ")
        message = input("Message: ")
        to_send = Message(self.username, self.receiver, message)
        self.s.sendall(bytes(str(to_send)).encode())
        pass

    def recieveMessage(self):
        data = self.s.recv(1024).decode()
        if data != "received": print(self.receiver + ":", data)
        else: print("Message sent successfully.") # tick.

    def serve(self):
        try:
            while True:
                input_streams = [sys.stdin, self.s]
                input = select(input_streams, [], [], 180) # remove timeout?
                
                if input == sys.stdin:
                    while self.receiver is None:
                        self.receiver = sys.stdin.readline()
                        self.display()
                    self.sendMessage()
                else:
                    self.recieveMessage()
                    self.display()
        except KeyboardInterrupt:
            print("Exiting")
            self.s.close()

    def display(self):
        sys.stdout.write("Me: ")
        sys.stdout.flush()        

client = Client()
client.login()
client.serve()