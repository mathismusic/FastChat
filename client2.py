import socket
import json
import sys
import ast
import datetime
import select
from color_codes import *
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from crypto import Crypt
from message import Message
from globals import Globals

class Client:
    """
    This represents the Client/User of the app. Consists of attributes host, port of server and 
    (unique) username of client, along with a 'receiver' which is the current receiver. 
    """

    def __init__(self) -> None:
        """Constructor"""
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # the client's socket
        self.HOST = Globals.default_host  # The server's hostname or IP address
        self.PORT = 61001 if len(sys.argv) == 1 else 61002  # The port used by the server
        self.LB_HOST = Globals.default_host  # The load balancer's hostname or IP address
        self.LB_PORT = 61051 if len(sys.argv) == 1 else 61012  # The port used by the load balancer
        
        self.username = None
        self.receivers: dict[str, str] = {}
        self.inAGroup = False
        self.chat_id = -1

        self.sqlConnection = None # database connection object
        
        # connection to main server database (to access public keys and list of users)
        self.database_connection = psycopg2.connect(
            database='fastchat_users',
            host=self.HOST,
            user="postgres",
            password="password",
            port="5432"
        )
        self.cryptography = Crypt()
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
                hashed_password = self.cryptography.hash_string(password)
                login_data = {"Username" : username, "Password" : hashed_password, "Newuser" : newuser, "Private_Key" : priv_key, "Public_Key" : pub_key}
                self.s.sendall(json.dumps(login_data).encode())
                
                data = self.s.recv(1024).decode()
                print(data)
                if (data in ["invalid", ""]): # the "" is just in case the data doesn't make it to the client before the load balancer returns - okay weird bug to fix
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
                            """) # is UNIQUE required?
                self.sqlConnection.commit()
                curs.execute(""" CREATE TABLE history (
                                chat_id SERIAL,
                                FOREIGN KEY (chat_id) REFERENCES chats(chat_id),
                                sender_name VARCHAR(255) NOT NULL,
                                msg TEXT NOT NULL,
                                t TIMESTAMP NOT NULL
                                )
                            """) # Any other relevent name for time?
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
            
            # load pending messages onto the client's database
            m = self.s.recv(65536).decode() # change to iterative
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
        
        # database_curs = self.database_connection.cursor()
        # database_curs.execute("SELECT (groupmembers) from groups where groupname=(%s)", (self.receiver,))
        # members = database_curs.fetchall()
        # if members == "":
        #     print("Not supposed to happen, hmm")
        #     return
        # members = ast.literal_eval(members)
        
        for receiver in self.receivers:
            to_send = Message(self.username, receiver, input, None)
            self.cryptography.get_rsa_encrypt_key(self.receivers[receiver].encode())
            to_send = self.cryptography.main_encrypt(to_send)
            # print(to_send)
            
            self.s.sendall(str(to_send).encode())
            #### No need now, since self.receiver is checked already by get_recipient.
            # status = self.s.recv(1024).decode()
            # if status == "invalid_recipient": 
            #     print(BOLD_YELLOW + "This user doesn't use FastChat " if self.inAGroup else "this group does not exist on FastChat :/" + RESET)
            #     return

            curs = self.sqlConnection.cursor()
            curs.execute("SELECT (chat_id) FROM chats WHERE receiver=%s",(self.receiver,))
            chat_id = curs.fetchall()[0][0]
            curs.execute("INSERT INTO history (chat_id, sender_name, msg) VALUES (%s,%s,%s)",(chat_id,to_send.sender,to_send.message))
            self.sqlConnection.commit()
            curs.close()

    def receiveMessage(self):
        """
        Receives message, adding it into the chat history as well
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
        
        curs = self.sqlConnection.cursor()
        curs.execute("SELECT (chat_id) FROM chats WHERE receiver=%s",(self.receiver,))
        chat_id = curs.fetchall()[0][0]
        curs.execute("INSERT INTO history (chat_id, sender_name, msg) VALUES (%s,%s,%s)",(chat_id, data.sender, data.message))
        self.sqlConnection.commit()
        curs.close()
        
        if data.sender in self.receivers:
            sys.stdout.write(MAGENTA + ">>> " + BLUE + data.sender + ": " + GREEN + data.message + '\n' + RESET)
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
            print(BOLD_BLUE + "Thank you for using FastChat!" + RESET)
            self.s.close()
            self.sqlConnection.close()
            sys.exit(1)

    def display(self):
        """Prompt"""
        sys.stdout.write(MAGENTA + ">>> You: " + GREEN)
        sys.stdout.flush()     
        
    def add_recipient(self, name_of_user):
        curs = self.database_connection.cursor()
        curs.execute("""SELECT userpubkey FROM usercreds WHERE username=%s""", (name_of_user,))
        pub_key_string = curs.fetchall()
        if len(pub_key_string) == 0:
            curs.close()
            return False
        else:
            self.receivers[name_of_user] = pub_key_string
            curs.close()
            return True
            #self.cryptography.get_rsa_encrypt_key(pub_key_string[0][0].encode())
        
    def get_recipient(self):
        """Get all messages from history from a given contact, ordered by time, and display"""
        self.receivers={}
        
        while True:
            sys.stdout.write(CYAN + '\nChoose your chat (start with "-g" if it is a group, "-cg" to create a group): ' + BLUE) 
            rvr = sys.stdin.readline()[:-1]
            print(RESET)
            if rvr == self.username:
                print(GREEN + 'Self messaging is not enabled yet.' + RESET)
                continue
            if rvr in [None, ""]:
                continue
            
            if rvr[:3] == '-g ':
                rvr = 'group_' + rvr[3:] # that's how group names are stored in the database. We prepend the 'group_' tag to allow for a dm and a group name to be identical.
                cursor = self.database_connection.cursor()
                cursor.execute("""SELECT groupmembers FROM groups WHERE groupname=%s""", (rvr,))
                members = curs.fetchall()
                cursor.close()
                if len(members)==0:
                    print(BOLD_YELLOW + "This group doesn't exist" + RESET)
                    continue;
                else:
                    members = ast.literal_eval(members[0])
                    curs_to_insert = self.sqlConnection.cursor()
                    curs_to_insert.execute("""INSERT INTO chats (receiver) SELECT (%s) WHERE NOT EXISTS (SELECT FROM chats WHERE receiver=%s) ON CONFLICT DO NOTHING;""",(rvr,rvr))
                    self.sqlConnection.commit()
                    curs_to_insert.close()
                    for member in members:
                        if member!=self.username:
                            self.add_recipient(member)
                    
                    
            elif rvr[:4] == '-cg ':
                rvr = 'group_' + rvr[4:]
                cursor = self.database_connection.cursor()
                cursor.execute("""SELECT groupmembers FROM groups WHERE groupname=%s""", (rvr,))
                members = curs.fetchall()
                cursor.close()
                if len(members)==0:
                    self.create_group(rvr)
                else:
                    print(BOLD_YELLOW + "This group name already exist. Try another" + RESET)
                    continue; 
                
            else:
                if self.add_recipient(rvr):
                    curs_to_insert = self.sqlConnection.cursor()
                    curs_to_insert.execute("""INSERT INTO chats (receiver) SELECT (%s) WHERE NOT EXISTS (SELECT FROM chats WHERE receiver=%s) ON CONFLICT DO NOTHING;""",(rvr,rvr))
                    self.sqlConnection.commit()
                    curs_to_insert.close()
                else:
                    print(BOLD_YELLOW + "This user doesn't exist" + RESET)
                    continue;
            # check if recipient/group is actually present
            # database_connection = psycopg2.connect(
            #         database='fastchat_users',
            #         host=self.HOST,
            #         user="postgres",
            #         password="password",
            #         port="5432"
            # )
            # database_curs = database_connection.cursor()
            # if self.inAGroup:
            #     database_curs.execute("""SELECT group""")
            # else:
            #     database_curs.execute("""SELECT userpubkey FROM usercreds WHERE username=%s""", (self.receiver,))
            #     pub_key_string = database_curs.fetchall()
            # if len(pub_key_string) == 0:
            #     if self.receiver[:4] != '-cg ':
            #         print(BOLD_YELLOW + "This " + ("group" if self.receiver[:3] == '-g ' else "user") + " doesn't exist2." + RESET)
            #         continue
            # elif self.receiver[:4] == '-cg ': 
            #     print(BOLD_YELLOW + "This group already exists3, choose another one." + RESET)
            #     continue
            # elif not self.inAGroup:
            #     self.cryptography.get_rsa_encrypt_key(pub_key_string[0][0].encode())
            
            break
            
        wantsHistory = input(YELLOW + "Just a quick chat, or do you want to see previous messages? (type 'quick' if the former, else 'all') " + CYAN) # or simply press enter
        print(RESET)

        if wantsHistory in ['quick', '']:
            return

        curs = self.sqlConnection.cursor()
        curs.execute("SELECT (chat_id) FROM chats WHERE receiver=%s",(rvr,))
        chat_id = curs.fetchall()[0][0]
        curs.execute(f"SELECT (chat_id, sender_name, msg, t) FROM history WHERE chat_id={chat_id} ORDER BY t DESC LIMIT 20")
        messages = curs.fetchall()
        for message in reversed(messages):
            print(message) # color differently based on user or receiver sent
        curs.close()

    def create_group(self, groupname):
        print(CYAN + "How many more users would you like to add?: " + BLUE)
        num_to_add = int(input())
        admins = [self.username]
        i = 0
        while i < num_to_add:
            print(GREEN + "Username #" + str(i+1) + ": (say -x to skip this user and move on to the next)" + BLUE)
            name_of_user = input()
            if name_of_user == '-x':
                i += 1
                continue
            added_successfully = self.add_recipient(name_of_user)
            if added_successfully:
                while True:
                    print(RED + "Do you want to make this user an admin?(y/n): " + BLUE)
                    ans = input()
                    if ans == 'y': admins.append(name_of_user)
                    elif ans != 'n': continue
                    break
                i += 1
            else:
                print(BOLD_YELLOW + "This user doesn't use FastChat4." + RESET)


        curs = self.database_connection.cursor()
        curs.execute("""INSERT INTO groups (groupname, groupmembers, adminlist) VALUES (%s, %s, %s)""", (groupname, str(self.receivers), str(admins)))
        self.database_connection.commit()
        curs.close()
        curs = self.sqlConnection.cursor()
        curs.execute("""INSERT INTO chats (receiver) VALUES (%s)""", (groupname,))
        self.sqlConnection.commit()
        curs.close()

if __name__ == "__main__":
    client = Client()
    client.login()
    client.serve()
