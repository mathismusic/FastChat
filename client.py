import socket
import json
import sys
import select
from color_codes import *
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

class Message:
    """
    This is the standard format of all messages transferred between servers and clients.
    It is in standard JSON format with attributes Sender, Recipient and Message
    """
    def __init__(self, sender, rec, msg) -> None:
        self.sender =  sender
        self.recipient = rec
        self.message = msg
    
    def __repr__(self) -> str:
        return json.dumps({"Sender": self.sender, "Recipient": self.recipient, "Message": self.message})

class Client:
    """
    This represents the Client/User of the app. Consists of attributes host, port of server and 
    (unique) username of client, along with a 'receiver' which is the current receiver. 
    """

    def __init__(self) -> None:
        """Constructor"""
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # the client's socket
        self.HOST = "192.168.103.215"  # The server's hostname or IP address
        self.PORT = 61001 if len(sys.argv) == 1 else 61002  # The port used by the server
        self.username = None
        self.receiver = None # who is the client talking to. make receiver a class for dms and groups.
        self.sqlConnection = None # database connection object
        # add fields to remember username and password to auto-login next time. (use a local client-specific database/file to store local client stuff)
        
    def login(self) -> None:
        """Asks login details from user, and sends them to server for authentication.
        Enter -1 if new user. Also connects to the PostGRESQL server for database handling."""
        self.s.connect((self.HOST, self.PORT)) # go to port self.PORT on machine self.HOST
        try:
            while(True):
                username = input(BOLD_BLACK + "Username (type -1 to create an account): " + MAGENTA)
                newuser = (username == '-1')
                if newuser:
                    username = input(BOLD_BLACK + "Choose username: " + MAGENTA)
                password = input(BOLD_BLACK + ("Choose " if newuser else "") + "Password: " + MAGENTA)
                print(RESET)
                login_data = {"Username" : username, "Password" : password, "Newuser" : newuser}
                self.s.sendall(json.dumps(login_data).encode())
                
                data = self.s.recv(1024).decode()
                print(data)
                if (data == "invalid"):
                    print(CYAN + ("This username already exists, please try again." if newuser else "Invalid username or password, please try again.") + RESET)
                else: 
                    print()
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
                curs.execute("DROP DATABASE IF EXISTS " + username.lower())
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
                                receiver VARCHAR(255) NOT NULL UNIQUE
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
            sys.exit(1)

        self.username = username

    def sendMessage(self, input):
        """
        Sends message, which inserts into the message history of the sender
        :param: input - The message string
        """
        # recipient = input("Continue conversation with: ")
        to_send = Message(self.username, self.receiver, input)
        # print(to_send)
        
        self.s.sendall(str(to_send).encode())
        status = self.s.recv(1024).decode()
        if status == "invalid_recipient": 
            print(BOLD_YELLOW + "This user doesn't use FastChat :/" + RESET)
            return

        curs = self.sqlConnection.cursor()
        curs.execute("SELECT (chat_id) FROM chats WHERE receiver=%s",(self.receiver,))
        chat_id = curs.fetchall()[0][0]
        curs.execute("INSERT INTO history (chat_id, sender_name, msg) VALUES (%s,%s,%s)",(chat_id,to_send.sender,to_send.message))
        self.sqlConnection.commit()
        curs.close()

    def receiveMessage(self):
        """
        Receives message, adding it into the chat history of receiver
        """
        msg = self.s.recv(1024).decode()
        if msg is not None:
            try:data = json.loads(msg)
            except:print(YELLOW + "Error: " + RESET + msg + "\n\n")
        # self.receiver = data['Sender'] # update receiver to whoever sent the message
        
        curs = self.sqlConnection.cursor()
        curs.execute("SELECT (chat_id) FROM chats WHERE receiver=%s",(self.receiver,))
        chat_id = curs.fetchall()[0][0]
        curs.execute("INSERT INTO history (chat_id, sender_name, msg) VALUES (%s,%s,%s)",(chat_id, data['Sender'], data['Message']))
        self.sqlConnection.commit()
        curs.close()
        
        sys.stdout.write(MAGENTA + ">>> " + BLUE + data['Sender'] + ": " + data['Message'] + '\n' + RESET)
        sys.stdout.flush()

    def serve(self):
        """Main serve loop, specify who you would like to talk to, and -cd to change the recipient."""

        print(WHITE + GREEN_BACKGROUND + 'Welcome to the chat. Say -e to exit the chat at any time, or simply use ctrl+C.', end='' + RESET)
        self.get_recipient()
        self.display()

        try:
            while True:
                input_streams = [self.s, sys.stdin]
                inputs = select.select(input_streams, [], [], 180)[0] # remove timeout?
                
                for input in inputs:
                    if input is self.s:
                        print()
                        self.receiveMessage()
                        self.display()
                        
                    else:
                        input = sys.stdin.readline()[:-1]
                        if input == "-cd": # user would like to change the dm
                            self.receiver = None
                            self.get_recipient()
                        elif input == "-e": # user wants to exit
                            print(BOLD_BLUE + "Thank you for using FastChat!" + RESET)
                            return
                        else:
                            self.sendMessage(input)
                        self.display()
                        
        except KeyboardInterrupt:
            print(BOLD_HIGH_BLACK + "Exiting" + RESET)
            self.s.close()
            self.sqlConnection.close()
            sys.exit(1)

    def display(self):
        """Prompt"""
        sys.stdout.write(MAGENTA + ">>> You: " + GREEN)
        sys.stdout.flush()     

    def get_recipient(self):
        """Get all messages from history from a given contact, ordered by time, and display"""
        
        while True:
            sys.stdout.write(CYAN + '\nWhom do you want to talk to? ' + BLUE) 
            self.receiver = sys.stdin.readline()[:-1]
            print(RESET)
            if self.receiver == self.username:
                print(GREEN + 'Self messaging is not allowed yet.' + RESET)
                continue
            if self.receiver in [None, ""]:
                continue
            
            # add a method to check whether the receiver exists or not
            curs = self.sqlConnection.cursor()
            curs.execute("""INSERT INTO chats (receiver) SELECT (%s) WHERE NOT EXISTS (SELECT FROM chats WHERE receiver=%s) ON CONFLICT DO NOTHING;""",(self.receiver,self.receiver))
            self.sqlConnection.commit()
            curs.close()
            break
            
        wantsHistory = input(YELLOW + "Just a quick chat, or do you want to see previous messages? (type 'quick' if the former, else 'all') " + CYAN)
        print(RESET)

        if wantsHistory == 'quick':
            return

        # chat_id to be updated -> what?
        curs = self.sqlConnection.cursor()
        curs.execute("SELECT (chat_id) FROM chats WHERE receiver=%s",(self.receiver,))
        chat_id = curs.fetchall()[0][0]
        curs.execute(f"SELECT (chat_id, sender_name, msg, t) FROM history WHERE chat_id={chat_id} ORDER BY t LIMIT 20")
        messages = curs.fetchall()
        for message in messages:
            print(message) # color differently based on user or receiver sent
        curs.close()

client = Client()
client.login()
client.serve()
