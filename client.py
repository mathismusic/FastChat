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
        pass
    def login(self) -> None:
        pass

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((HOST, PORT))

    a=""
    # user login
    while(True):
        username = input("Username (-1 to create an account): ")
        newuser = (username == '-1')
        if newuser:
            username = input("Choose username: ")
        password = input(("Choose " if newuser else "") + "Password: ")
        login_data = {"Username" : username, "Password" : password, "Newuser" : newuser}
        s.sendall(json.dumps(login_data).encode())
        data = s.recv(1024).decode()
        if (data == "invalid"):
            print("This username already exists. Please try again." if newuser else "Invalid username, please try again.")
        else: break
    
    print(data)

    # messaging loop
    while(a!="exit"):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
        loop.close()
