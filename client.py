import socket
import json
import sys
import datetime
import select
from color_codes import *
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from crypto import Crypt
from message import Message

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
        self.LB_HOST = "192.168.103.215"  # The load balancer's hostname or IP address
        self.LB_PORT = 61051 if len(sys.argv) == 1 else 61012  # The port used by the load balancer
        
        self.username = None
        self.receiver = None # who is the client talking to. make receiver a class for dms and groups.
        self.sqlConnection = None # database connection object
        self.cryptography = Crypt() #cryptography object
        # add fields to remember username and password to auto-login next time. (use a local client-specific database/file to store local client stuff)
        
    def login(self) -> None:
        """Asks login details from user, and sends them to server for authentication.
        Enter -1 if new user. Also connects to the PostGRESQL server for database handling."""
        self.s.connect((self.LB_HOST, self.LB_PORT)) # go to port self.PORT on machine self.HOST
        try:
            while(True):
                username = input(BOLD_BLACK + "Username (type -1 to create an account): " + MAGENTA)
                newuser = (username == '-1')
                if newuser:
                    username = input(BOLD_BLACK + "Choose username: " + MAGENTA)
                password = input(BOLD_BLACK + ("Choose " if newuser else "") + "Password: " + MAGENTA)
                print(RESET)
                
                priv_key = None
                pub_key = None
                if newuser:
                    self.cryptography.gen_rsa_key()
                    priv_key = self.cryptography.get_rsa_private_str(password).decode()
                    pub_key = self.cryptography.get_rsa_public_str().decode()
                
                login_data = {"Username" : username, "Password" : password, "Newuser" : newuser, "Private_Key" : priv_key, "Public_Key" : pub_key}
                self.s.sendall(json.dumps(login_data).encode())
                
                data = self.s.recv(1024).decode()
                print(data)
                if (data == "invalid"):
                    print(CYAN + ("This username already exists, please try again." if newuser else "Invalid username or password, please try again.") + RESET)
                else: 
                    print(data)
                    server_data = json.loads(data)
                    self.s.close()
                    self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self.s.connect((server_data['hostname'], int(server_data['port'])))
                    self.s.sendall(json.dumps({"Username": username}).encode())
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
                curs.execute("""CREATE TABLE privatekey (
                                privkey TEXT NOT NULL
                                )
                            """)
                self.sqlConnection.commit()
                curs.execute("""INSERT INTO privatekey (privkey) VALUES (%s)""", (priv_key,))
                self.sqlConnection.commit()

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
                
                curs = self.sqlConnection.cursor()
                curs.execute("""SELECT privkey FROM privatekey""")
                encrypted_bytes = curs.fetchall()[0][0].encode()
                self.cryptography.set_priv_key(password, encrypted_bytes)

            print(self.sqlConnection)
            
            m = self.s.recv(65536).decode()
            msgs = json.loads(m)
            
            for msg in msgs:
                # pendingmsg = self.s.recv(1024).decode()
                # msg = json.loads(pendingmsg)
                d = json.loads(msg[1])
                curs = self.sqlConnection.cursor()
                curs.execute("""INSERT INTO chats (receiver) SELECT (%s) WHERE NOT EXISTS (SELECT FROM chats WHERE receiver=%s) ON CONFLICT DO NOTHING;""",(d['Sender'],d['Sender']))
                self.sqlConnection.commit()
                curs.execute("SELECT (chat_id) FROM chats WHERE receiver=%s",(d['Sender'],))
                chat_id = curs.fetchall()[0][0]
                curs.execute("INSERT INTO history (chat_id, sender_name, msg, t) VALUES (%s,%s,%s,%s)",(chat_id,d['Sender'],d['Message'],datetime.datetime.strptime(msg[2], '%Y-%m-%d %H:%M:%S.%f')))
                self.sqlConnection.commit()
                curs.close()
                

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
        to_send = Message(self.username, self.receiver, input, None)
        to_send = self.cryptography.main_encrypt(to_send)
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
        msg = self.s.recv(8192).decode()
        data = {}
        if msg in [None, ""]:
            print(YELLOW + "msg: " + RESET + "|" + msg + "|")
            return

        print(YELLOW + "msg: " + RESET + "|" + msg + "|")
        data = json.loads(msg)   
        data = self.cryptography.main_decrypt(Message(data['Sender'], data['Recipient'], data['Message'], data['Key'])) 
        print(YELLOW + "data: " + RESET + "|" + str(data) + "|\n\n")
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
            

            #check if recipient is actually present
            usercreds_connection = psycopg2.connect(
                    database='fastchat_users',
                    host=self.HOST,
                    user="postgres",
                    password="password",
                    port="5432"
            )
            usercreds_curs = usercreds_connection.cursor()
            usercreds_curs.execute("""SELECT userpubkey FROM usercreds WHERE username=%s""", (self.receiver,))
            pub_key_string = usercreds_curs.fetchall()
            if(len(pub_key_string) == 0):
                print("This user doesn't exist")
                continue
            else:
                self.cryptography.get_rsa_encrypt_key(pub_key_string[0][0].encode())

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
        curs.execute(f"SELECT (chat_id, sender_name, msg, t) FROM history WHERE chat_id={chat_id} ORDER BY t DESC LIMIT 20")
        messages = curs.fetchall()
        for message in reversed(messages):
            print(message) # color differently based on user or receiver sent
        curs.close()

if __name__ == "__main__":
    client = Client()
    client.login()
    client.serve()
