# echo-client.py

import socket
import json
import sys
from select import select
#from color_codes import *
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

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
        self.HOST = "192.168.103.215"  # The server's hostname or IP address
        self.PORT = 61002  # The port used by the server
        self.username = None
        self.receiver = None # who is the client talking to. make receiver a class for dms and groups.
        self.sqlConnection = None # database connection object
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
                else: 
                    break

            if newuser:
                self.sqlConnection = psycopg2.connect(
                    host=self.HOST,
                    user="postgres",
                    password="password",
                    port="5432"
                )
                self.sqlConnection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
                curs = self.sqlConnection.cursor()
                curs.execute("CREATE DATABASE " + username.lower())
                self.sqlConnection.commit()
                self.sqlConnection.close()

                self.sqlConnection = psycopg2.connect(
                    database=username,
                    host=self.HOST,
                    user="postgres",
                    password="password",
                    port="5432"
                )
                curs = self.sqlConnection.cursor()
                curs.execute("""CREATE TABLE chats (
                                chat_id SERIAL PRIMARY KEY,
                                receiver VARCHAR(255) NOT NULL
                                )
                            """)
                self.sqlConnection.commit()
                curs.execute(""" CREATE TABLE history (
                                chat_id SERIAL,
                                FOREIGN KEY (chat_id) REFERENCES chats(chat_id),
                                sender_name VARCHAR(255) NOT NULL,
                                msg TEXT NOT NULL,
                                t TIMESTAMP NOT NULL
                                )
                            """) # Any otherrelevent name for time ?
                curs.execute("""ALTER TABLE history ALTER COLUMN t SET DEFAULT now();""")
                self.sqlConnection.commit()
                curs.close()
            else:
                self.sqlConnection = psycopg2.connect(
                    database=username,
                    host=self.HOST,
                    user="postgres",
                    password="password",
                    port="5432"
                )

            print(self.sqlConnection)

        except KeyboardInterrupt:
            print("Caught keyboard interrupt, exiting")

        self.username = username

    def sendMessage(self, input):
        # recipient = input("Continue conversation with: ")
        to_send = Message(self.username, self.receiver, input)
        print(to_send)
        
        curs = self.sqlConnection.cursor()
        curs.execute(f"SELECT (chat_id) FROM chats WHERE reciever={self.receiver}")
        chat_id = curs.fetchall()[0][0]
        curs.execute(f"INSERT INTO history (chat_id, sender_name, msg) VALUES ({chat_id},{to_send.sender},{to_send.message})")
        self.sqlConnection.commit()
        curs.close()
        
        self.s.sendall(str(to_send).encode())
        status = self.s.recv(1024).decode()
        if status == "invalid_recipient": 
            print("This user doesn't use FastChat :)")

    def receiveMessage(self):
        data = json.loads(self.s.recv(1024).decode())
        # self.receiver = data['Sender'] # update receiver to whoever sent the message
        
        curs = self.sqlConnection.cursor()
        curs.execute(f"SELECT (chat_id) FROM chats WHERE reciever={self.receiver}",)
        chat_id = curs.fetchall()[0][0]
        curs.execute(f"INSERT INTO history (chat_id, sender_name, msg) VALUES ({chat_id}, {data['Sender']}, {data['Message']}")
        self.sqlConnection.commit()
        curs.close()
        
        sys.stdout.write(data['Sender'] + ": " + data['Message'] + '\n')
        sys.stdout.flush()

    def serve(self):
        print('Welcome to the chat. Say -e to exit the chat at any time, or simply use ctrl+C.', end='')
        self.get_recipient()
        self.display()

        try:
            while True:
                input_streams = [self.s, sys.stdin]
                inputs = select(input_streams, [], [], 180)[0] # remove timeout?
                
                for input in inputs:
                    if input is self.s:
                        self.receiveMessage()
                        self.display()
                        
                    else:
                        input = sys.stdin.readline()[:-1]
                        if input == "-cd": # user would like to change the dm
                            self.receiver = None
                            self.get_recipient()
                        else:
                            self.sendMessage(input)
                        self.display()
                        
        except KeyboardInterrupt:
            print("Exiting")
            self.s.close()
            self.sqlConnection.close()

    def display(self):
        sys.stdout.write(">>> ")
        sys.stdout.flush()     

    def get_recipient(self):
        sys.stdout.write('\nWhom do you want to talk to? ') 
        while True:
            self.receiver = sys.stdin.readline()[:-1]
            if self.receiver not in [None, ""]:
                # add a method to check whether the reciever exists or not
                curs = self.sqlConnection.cursor()
                curs.execute(f"INSERT INTO chats (receiver) VALUES ({self.receiver})")
                self.sqlConnection.commit()
                curs.close()
                break
            
        # chat_id to be updated
        curs = self.sqlConnection.cursor()
        curs.execute(f"SELECT (chat_id) FROM chats WHERE reciever={self.receiver}")
        chat_id = curs.fetchall()[0][0]
        curs.execute(f"SELECT ({chat_id}, sender_name, msg, t) FROM history ORDER BY t LIMIT 20")
        messeges = curs.fetchall()
        for message in messeges:
            print(message)
        curs.close()

client = Client()
client.login()
client.serve()