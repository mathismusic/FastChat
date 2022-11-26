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
from message import *
import binascii
import os

class Client:
    """
    This represents the Client/User of the app. Consists of attributes host, port of server and 
    (unique) username of client, along with a 'receiver' which is the current receiver. Also contains 
    the socket, database connection and the IO Selector attributes. Contains a Crypt object for cryptography.
    """

    def __init__(self, db_host, lb_host, database) -> None:
        """Constructor, connects to the main server database. Sets host/port attributes.

        :param: database: The name of the main users database
        :type: database: str
        """
        self.s = None # the client's socket
        self.DB_HOST = db_host
        self.LB_HOST = lb_host  # The load balancer's hostname or IP address
        self.LB_PORT = 61051 # The port used by the load balancer
        self.handler = None
        self.username = None
        self.password = None
        self.receivers: dict[str, str] = {} # receiver to their public key
        self.database = database
        self.inAGroup = False
        self.group_name = None
        self.isAdmin = False
        self.events = []
        self.sqlConnection = None # database connection object
        
        # connection to main server database (to access public keys and list of users)
        self.database_connection = psycopg2.connect(
            database=self.database,
            host=self.DB_HOST,
            user="postgres",
            password="password",
            port="5432"
        )
        self.cryptography = Crypt() 
        
        #  TODO if time: add fields to remember username and password to auto-login next time. (use a local client-specific database/file to store local client stuff)
        
    def login(self) -> None:
        """Asks login details from user, and sends them to server for authentication.
        Enter -1 if new user. Also connects to the personal PostGRESQL server on cloud
        for database handling. Pending messages are fetched and stores in the personal database.
        Generates the RSA tokens for new users."""
         
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.connect((self.LB_HOST, self.LB_PORT)) 
        try:

            while True:
                try:
                    username = input(BOLD_BLACK + "Username (type -1 to create an account): " + MAGENTA)
                    newuser = (username == '-1')
                    if newuser:
                        username = input(BOLD_BLACK + "Choose username: " + MAGENTA)
                    password = input(BOLD_BLACK + ("Choose " if newuser else "") + "Password: " + MAGENTA)
                    self.password = password
                    self.username = username
                    print(RESET)
                    
                    priv_key = None
                    pub_key = None
                    if newuser:
                        self.cryptography.gen_rsa_key()
                        priv_key = self.cryptography.get_rsa_private_str(password).decode()
                        pub_key = self.cryptography.get_rsa_public_str().decode()
                    hashed_password = self.cryptography.hash_string(password)
                    login_data = {"Username" : username, "Password" : hashed_password, "Newuser" : newuser, "Private_Key" : priv_key, "Public_Key" : pub_key}
                    
                    self.handler = MessageHandler(self.s, (self.LB_HOST, self.LB_PORT))
                    self.handler.write(login_data)
                    
                    data = self.handler.read()
                    if (data == "invalid"): # the "" is just in case the data doesn't make it to the client before the load balancer exits
                        print(CYAN + ("This username already exists, please try again." if newuser else "Invalid username or password, please try again.") + RESET)
                    elif(data == ""):
                        print("Connection to server lost")
                    else:
                        # print(data)
                        if self.s:
                            self.s.close()
                        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        self.s.connect((data['hostname'], int(data['port'])))
                        self.handler = MessageHandler(self.s, (data['hostname'], int(data['port'])), "Server")
                        self.handler.write({"Username": username})
                        # print(username)
                        self.s.setblocking(True)
                        # data = SimpleNamespace(username = "Server", outb=[{"Username": username}],inb=[])
                        # self.selector.register(fileobj=self.s,events= selectors.EVENT_READ ,data=data)
                        break
                except KeyboardInterrupt:
                    print(BOLD_BLUE + "\nThank you for using FastChat!" + RESET)
                    if self.s:
                        self.s.close()
                    sys.exit(1)    
                            
            
            ### outside the while loop ###
            
            # make the local databases for a new user
            if newuser:
                self.sqlConnection = psycopg2.connect(
                    host=self.DB_HOST,
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
                    host=self.DB_HOST,
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
                                msg_id SERIAL PRIMARY KEY,
                                chat_id SERIAL,
                                FOREIGN KEY (chat_id) REFERENCES chats(chat_id),
                                sender_name VARCHAR(255) NOT NULL,
                                msg TEXT NOT NULL,
                                fernetkey TEXT NOT NULL,
                                t TIMESTAMP NOT NULL
                                )
                            """) # Any other relevent name for time?
                curs.execute("""ALTER TABLE history ALTER COLUMN t SET DEFAULT now();""")
                self.sqlConnection.commit()
                curs.close()
            else:
                curs = self.database_connection.cursor()
                self.sqlConnection = psycopg2.connect(
                    database=username,
                    host=self.DB_HOST,
                    user="postgres",
                    password="password",
                    port="5432"
                )
                
                curs = self.sqlConnection.cursor()
                curs.execute("""SELECT privkey FROM privatekey""")
                encrypted_bytes = curs.fetchall()[0][0].encode()
                self.cryptography.set_priv_key(password, encrypted_bytes)

            # print(self.sqlConnection)
            
            # load pending messages onto the client's database
            size = self.handler.read() # change to iterative
            # print(int(size))
            for i in range(int(size)):
                # pendingmsg = self.s.recv(1024).decode()
                # msg = json.loads(pendingmsg)
                if self.handler._recv_buffer:
                    d = self.handler.read(True)
                else:
                    d = self.handler.read(False)
                msg = json.loads(d[1])
                # decrypt the message, then encrypt with password to store in history
                msg_obj = Message(msg['Sender'], msg['Recipient'], msg['Message'], msg['Key'], msg['Group_Name'])
                msg_obj = self.cryptography.main_decrypt(msg_obj)
                #encrypt with password
                msg_obj = self.cryptography.password_encrypt(self.password, msg_obj)
                curs = self.sqlConnection.cursor()
                rvr = msg['Sender'] if not msg['Group_Name'] else msg['Group_Name']
                curs.execute("""INSERT INTO chats (receiver) SELECT (%s) WHERE NOT EXISTS (SELECT FROM chats WHERE receiver=%s) ON CONFLICT DO NOTHING;""",(rvr,rvr))
                self.sqlConnection.commit()
                curs.execute("SELECT chat_id FROM chats WHERE receiver=%s",(rvr,))
                chat_id = curs.fetchall()[0][0]
                curs.execute("INSERT INTO history (chat_id, sender_name, msg, fernetkey, t) VALUES (%s,%s,%s,%s,%s)",(chat_id,msg_obj.sender,msg_obj.message, msg_obj.fernet_key, datetime.datetime.strptime(d[2], '%Y-%m-%d %H:%M:%S.%f')))
                self.sqlConnection.commit()
                curs.close()
                    

        except KeyboardInterrupt:
            print(BOLD_BLUE + "\nThank you for using FastChat!" + RESET)
            if self.s:
                self.s.close()
            self.sqlConnection.close()
            sys.exit(1)
        
    def sendMessage(self, input):
        """
        Sends message after RSA encryption,
        and inserts into sender's history after password encryption

        :param: input - The message string
        :type: input str
        """
        
        for receiver in self.receivers:
            to_send = Message(self.username, receiver, input, None, self.group_name if self.inAGroup else None)
            #print(self.receivers[receiver])
            self.cryptography.get_rsa_encrypt_key((self.receivers[receiver]).encode())
            encrypted_to_send = self.cryptography.main_encrypt(to_send)
            to_send.fernet_key = self.cryptography.fernet_encrypt_key.decode()
            to_store = self.cryptography.password_encrypt(self.password, to_send)
            # print(to_send)
            
            self.handler.write(encrypted_to_send.get_json())

            curs = self.sqlConnection.cursor()
            if self.inAGroup:
                curs.execute("SELECT chat_id FROM chats WHERE receiver=%s",(self.group_name,))
            else:
                curs.execute("SELECT chat_id FROM chats WHERE receiver=%s",(receiver,))
            chat_id = curs.fetchall()[0][0]
            if not self.inAGroup:
                curs.execute("INSERT INTO history (chat_id, sender_name, msg, fernetkey) VALUES (%s,%s,%s,%s)",(chat_id,to_store.sender,to_store.message, to_store.fernet_key))
                self.sqlConnection.commit()
                
        if self.inAGroup:
            curs.execute("INSERT INTO history (chat_id, sender_name, msg, fernetkey) VALUES (%s,%s,%s,%s)",(chat_id,to_store.sender,to_store.message, to_store.fernet_key))
            self.sqlConnection.commit()
        curs.close()

    def receiveMessage(self, tag=False):
        """
        Receives message, decrypts it and adds it into the chat history after password encryption. 
        """
        msg = self.handler.read(tag)
        # print(msg)
        data = {}
        if msg in [None, ""]:
            print(YELLOW + "msg: " + RESET + "|" + str(msg) + "|")
            return            

        data = msg           
        data = self.cryptography.main_decrypt(Message(data['Sender'], data['Recipient'], data['Message'], data['Key'], data['Group_Name'])) 
        to_store = self.cryptography.password_encrypt(self.password, data)
        
        curs = self.sqlConnection.cursor()

        rec = data.group_name if data.group_name else data.sender
        curs.execute("SELECT chat_id FROM chats WHERE receiver=%s",(rec,))
        tmp = curs.fetchall()
        if len(tmp) == 0:
            curs.execute("INSERT INTO chats (receiver) VALUES (%s)", (rec,))
            curs.execute("SELECT chat_id FROM chats WHERE receiver=%s",(rec,))
            tmp = curs.fetchall()
        chat_id = tmp[0][0]
        curs.execute("INSERT INTO history (chat_id, sender_name, msg, fernetkey) VALUES (%s,%s,%s,%s) RETURNING t",(chat_id, to_store.sender, to_store.message, to_store.fernet_key))
        timestamp = curs.fetchone()[0]
        self.sqlConnection.commit()
        curs.close()

        if self.inAGroup and data.group_name==self.group_name:

            if data.message[:9]=="__added__":
                newGuy = data.message[9:]
                curs = self.database_connection.cursor()
                curs.execute("SELECT userpubkey FROM \"usercreds\" WHERE username=%s",(newGuy,))
                rvr_pub_key = curs.fetchall()[0][0]
                self.receivers[newGuy] = rvr_pub_key
                curs.close()
            
            elif data.message[:9]=="__removed__":
                removedGuy = data.message[9:]
                if removedGuy == self.username:
                    # self.add_notification("You were added to the group " + data.group_name[6:])
                    sys.stdout.write(MAGENTA + ">>> " + BLUE + data.sender + ": " + GREEN + data.message + '\n' + RESET)
                    sys.stdout.flush()
                    self.get_recipient()
                # else:
                #     self.add_notification(data.sender + " added " + removedGuy + " to the group " + data.group_name[6:])
                self.receivers.pop(removedGuy)
                sys.stdout.write(MAGENTA + ">>> " + BLUE + data.sender + ": " + GREEN + data.message + '\n' + RESET)
                sys.stdout.flush()
                
            elif (data.message[:9] == "__image__"):
                self.receive_img(data, timestamp)
            else:
                sys.stdout.write(MAGENTA + ">>> " + BLUE + data.sender + ": " + GREEN + data.message + '\n' + RESET)
                sys.stdout.flush()
        
        elif not self.inAGroup and data.group_name is None and data.sender in self.receivers:
            if (data.message[:9] == "__image__"):
                self.receive_img(data, timestamp)
            else:
                sys.stdout.write(MAGENTA + ">>> " + BLUE + data.sender + ": " + GREEN + data.message + '\n' + RESET)
                sys.stdout.flush()
        
        if self.handler._recv_buffer:
            self.receiveMessage(tag=True)
        
    def serve(self):
        """Main loop, specify who you would like to talk to, and talk!
        Flags
        
        - -e   - Exit
        - -cd  - Change the chat
        - -add - Add member to current group
        - -del - Delete member from current group
        - -img - Send an image. The image file's relative path must be provided.
        """
        self.events.append(self.s)
        self.events.append(sys.stdin)
        
        print(WHITE + GREEN_BACKGROUND + 'Welcome to the chat. Say -e to exit the chat at any time, or simply use ctrl+C.' + RESET)
        print(BOLD_YELLOW + "Flags:\n" + BOLD_GREEN + """
        - -e   - Exit
        - -cd  - Change the chat
        - -add - Add member to current group
        - -del - Delete member from current group
        - -img - Send an image. The image file's relative path must be provided.
        """ + RESET)
        self.get_recipient()
        self.display()
        
        try:
            while True:
                readable_events, _, _ = select.select(self.events, [], [])
                for readable_event in readable_events:
                    if readable_event == self.s:
                        print()
                        self.receiveMessage()
                        self.display()
                    else:
                        usr_input = sys.stdin.readline()[:-1]
                        
                        # check bunch of flags (stuff you would do using the gui on whatsapp)
                        if usr_input == "-cd": # user would like to change the dm/grp
                            self.receivers = {}
                            self.get_recipient()
                        elif usr_input == "-e": # user wants to exit
                            if self.s:
                                self.s.close()
                            print(BOLD_BLUE + "Thank you for using FastChat!" + RESET)
                            if self.s:
                                self.s.close()
                            return
                        elif usr_input == "-add": # user wants to add member to group
                            self.add_member()
                        elif usr_input == "-del": # user wants to delete member from group
                            self.delete_member()

                        elif usr_input == "-img":
                            filepath = input(YELLOW + "Relative Path: " + GREEN)
                            img_to_send = open(filepath, "rb")
                            img_str ="__image__" + binascii.hexlify(img_to_send.read()).decode()
                            self.sendMessage(img_str)
                            
                        else:                        
                            self.sendMessage(usr_input)
                        self.display()

        except KeyboardInterrupt:
            print(BOLD_BLUE + "\nThank you for using FastChat!" + RESET)
            if self.s:
                self.s.close()
            self.sqlConnection.close()
            sys.exit(1)
        
    def display(self):
        """User prompt"""
        sys.stdout.write(MAGENTA + ">>> You: " + GREEN)
        sys.stdout.flush()     
        
    def add_recipient(self, name_of_user):
        """
        Used to add a member to a group

        :param: name_of_user: Name of the user to add to the group
        :type: name_of_user str
        """
        curs = self.database_connection.cursor()
        curs.execute("""SELECT userpubkey FROM usercreds WHERE username=%s""", (name_of_user,))
        pub_key_string = curs.fetchall()
        if len(pub_key_string) == 0:
            curs.close()
            return False
        else:
            self.receivers[name_of_user] = pub_key_string[0][0]
            curs.close()
            return True
            
    def get_recipient(self):
        """Get all messages from history from a given contact or group,
        ordered by time, and display after password decryption.
        Supports quickchat if history isn't demanded."""
        self.receivers={}
        
        while True:
            try:
                sys.stdout.write(CYAN + '\nChoose your chat (start with "-g " if it is a group, "-cg " to create a group): ' + BLUE) 
                rvr = sys.stdin.readline()[:-1]
                print(RESET)
                if rvr == self.username:
                    print(GREEN + 'Self messaging is not enabled yet.' + RESET)
                    continue
                if rvr in [None, ""]:
                    continue
                
                if rvr == '-e':
                    print("Saving your pending messages, Please Wait")
                    isReadable, _, _ = select.select([self.s], [], [], 0.1)
                    if len(isReadable):
                        self.receiveMessage()
                    if self.s:
                        self.s.close()
                    print(BOLD_BLUE + "Thank you for using FastChat!" + RESET)
                    if self.s:
                        self.s.close()
                    sys.exit(1)
                if rvr[:3] == '-g ':
                    rvr = 'group_' + rvr[3:] # that's how group names are stored in the database. We prepend the 'group_' tag to allow for a dm and a group name to be identical.                
                    cursor = self.database_connection.cursor()
                    cursor.execute("""SELECT groupmembers, adminlist FROM groups WHERE groupname=%s""", (rvr,))
                    grp_data = cursor.fetchall()
                    cursor.close()
                    if len(grp_data) == 0:
                        print(BOLD_YELLOW + "This group doesn't exist" + RESET)
                        continue
                    
                    adminlist = ast.literal_eval(grp_data[0][1])
                    members = ast.literal_eval(grp_data[0][0])
                    if self.username not in members:
                        print(BOLD_YELLOW  + "You are not a participant of this group" + RESET)
                        continue
                    
                    curs_to_insert = self.sqlConnection.cursor()
                    curs_to_insert.execute("""INSERT INTO chats (receiver) SELECT (%s) WHERE NOT EXISTS (SELECT FROM chats WHERE receiver=%s) ON CONFLICT DO NOTHING;""",(rvr,rvr))
                    self.sqlConnection.commit()
                    curs_to_insert.close()
                    for member in members:
                        if member == self.username:
                            continue
                        self.add_recipient(member)
                    if self.username in adminlist:
                        self.isAdmin = True
                    self.inAGroup = True
                    self.group_name = rvr

                elif rvr[:4] == '-cg ':
                    rvr = 'group_' + rvr[4:]
                    cursor = self.database_connection.cursor()
                    cursor.execute("""SELECT groupmembers FROM groups WHERE groupname=%s""", (rvr,))
                    members = cursor.fetchall()
                    cursor.close()
                    if len(members)==0:
                        self.group_name = rvr
                        self.create_group(rvr)
                        self.isAdmin = True
                    else:
                        print(BOLD_YELLOW + "This group name already exists. Try another" + RESET)
                        continue; 
                
                else:
                    if self.add_recipient(rvr):
                        curs_to_insert = self.sqlConnection.cursor()
                        curs_to_insert.execute("""INSERT INTO chats (receiver) SELECT (%s) WHERE NOT EXISTS (SELECT FROM chats WHERE receiver=%s) ON CONFLICT DO NOTHING;""",(rvr,rvr))
                        self.sqlConnection.commit()
                        curs_to_insert.close()
                    else:
                        print(BOLD_YELLOW + "This user doesn't exist" + RESET)
                        continue
                    self.inAGroup = False
                break

            except KeyboardInterrupt as e:
                print("Saving your pending messages, Please Wait")
                isReadable, _, _ = select.select([self.s], [], [], 0.1)
                if len(isReadable):
                    self.receiveMessage()
                print(BOLD_BLUE + "\nThank you for using FastChat!" + RESET)
                isReadable, _, _ = select.select([self.s],[],[])
                if len(isReadable):
                    self.receiveMessage()
                if self.s:
                    self.s.close()
                self.sqlConnection.close()
                sys.exit(1)
            
        wantsHistory = input(YELLOW + "Just a quick chat, or do you want to see previous messages? (type 'quick - or simply enter' if the former, else 'all') " + CYAN) # or simply press enter
        print(RESET)

        if wantsHistory in ['quick', '']:
            return

        curs = self.sqlConnection.cursor()
        curs.execute("SELECT chat_id FROM chats WHERE receiver=%s",(rvr,))
        chat_id = curs.fetchall()[0][0]
        curs.execute("SELECT chat_id, sender_name, msg, fernetkey,t FROM history WHERE chat_id=%s ORDER BY t DESC LIMIT 20", (chat_id,))
        messages = curs.fetchall()
        for message in reversed(messages):
            msg_obj = Message(message[1], self.username, message[2], message[3], rvr if not self.inAGroup else rvr[6:])
            msg_obj = self.cryptography.password_decrypt(self.password, msg_obj)
            to_print = msg_obj.message
            if to_print[:9] == "__image__":
                self.receive_img(msg_obj, message[4])
            else:
                print(MAGENTA + ">>> " + ("You: " if message[1] == self.username else BLUE + message[1] + ": ") + GREEN + to_print) # color differently based on user or receiver sent
        if len(messages) > 0:
            print(CYAN + "------END HISTORY------" + RESET)
        curs.close()

    def create_group(self, groupname):
        """
        Create a group. Prompts for number of people and then for usernames.
        Supports multiple admins.

        :param: groupname: The name of the group
        :type: groupname str
        """

        print(CYAN + "How many more users would you like to add?: " + BLUE)
        num_to_add = int(input())
        admins = [self.username]
        i = 0
        while i < num_to_add:
            name_of_user = input(GREEN + "Username #" + str(i+1) + ": (say -x to skip this user and move on to the next): " + BLUE)
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
        curs.execute("""INSERT INTO groups (groupname, groupmembers, adminlist) VALUES (%s, %s, %s)""", (groupname, str([self.username] + list(self.receivers.keys())), str(admins)))
        self.database_connection.commit()
        curs.close()
        curs = self.sqlConnection.cursor()
        curs.execute("""INSERT INTO chats (receiver) VALUES (%s)""", (groupname,))
        self.sqlConnection.commit()
        curs.close()
        self.inAGroup = True

    def add_member(self):
        """
        Add a member to the current group, called when the '-add' flag is given.
        """
        if not self.inAGroup:
            print(YELLOW + "Cannot add a member to a DM, of course :)" + RESET)
            return

        if not self.isAdmin:
            print(YELLOW + "You are not an Admin, so cannot add members to the group" + RESET)
            return

        added_is_admin = False
        added_successfully = False
        while True:
            name_of_user = input(RED + "Whom would you like to add? (type -x if you want to go back): " + GREEN)
            if name_of_user == '-x':
                print(RESET)
                return
            added_successfully = self.add_recipient(name_of_user)
            if not added_successfully: 
                print(BOLD_YELLOW + "This user doesn't use FastChat, try again." + RESET)
                continue
            while True:
                print(RED + "Do you want to make this user an admin?(y/n): " + BLUE)
                ans = input()
                if ans == 'y': added_is_admin = True
                elif ans != 'n': continue
                break
            break

        curs = self.database_connection.cursor() 
        curs.execute("""SELECT groupmembers, adminlist FROM groups WHERE groupname=%s""", (self.group_name,))
        data = curs.fetchall()
        groupmembers_new = ast.literal_eval(data[0][0])
        groupmembers_new.append(name_of_user)

        self.sendMessage("__added__"+name_of_user)

        groupadmins_new = ast.literal_eval(data[0][1])
        if added_is_admin:
            groupadmins_new.append(name_of_user)
        curs.execute("""UPDATE groups SET groupmembers=%s, adminlist=%s WHERE groupname=%s""", (str(groupmembers_new), str(groupadmins_new), self.group_name))
        self.database_connection.commit()
        curs.close()
        print(BLUE + "Successfully added member " + GREEN + name_of_user + BLUE + "!" + RESET)

    def delete_member(self):
        """
        Delete a member from the current group. Is called when the '-del' flag is given.
        """
        if not self.inAGroup:
            print(YELLOW + "Cannot delete a member from a DM, of course :)" + RESET)
            return

        if not self.isAdmin:
            print(YELLOW + "You are not an Admin, so cannot delete members from the group" + RESET)
            return

        while True:
            name_of_user = input(RED + "Whom would you like to delete (type -x if you want to go back)? " + GREEN)
            if name_of_user == '-x':
                print(RESET)
                return
            if name_of_user not in self.receivers:
                print(YELLOW + "This user isn't part of this group, try again." + RESET)
                continue
            break

        self.sendMessage("__removed__" + name_of_user)

        curs = self.database_connection.cursor()
        curs.execute("""SELECT groupmembers, adminlist FROM groups WHERE groupname=%s""", (self.group_name,))
        data = curs.fetchall()
        groupmembers_new = ast.literal_eval(data[0][0])
        groupmembers_new.remove(name_of_user)
        groupadmins_new = str(groupadmins_new)
        admins = ast.literal_eval(data[0][1])
        if name_of_user in admins:
            groupadmins_new = ast.literal_eval(data[0][1])
            groupadmins_new.remove(name_of_user)
            groupadmins_new = str(groupadmins_new)
        curs.execute("""UPDATE groups SET groupmembers=%s, adminlist=%s WHERE groupname=%s""", (groupmembers_new, groupadmins_new, self.group_name))
        self.database_connection.commit()
        curs.close()
        self.receivers.pop(name_of_user)
        print(BLUE + "Successfully deleted member " + GREEN + name_of_user + BLUE + "!" + RESET)
        print([self.username] + list(self.receivers.keys()))

    def receive_img(self, data, timestamp):
        sent = "sent" if (data.sender == self.username) else "received"
        folder = "sent_imgs" if sent == "sent" else "received_imgs"
        imgfilename = f"{folder}/{data.sender}_{data.group_name[:6] + '_' if data.group_name else ''}_{str(timestamp)}.png"
        print(f"You {sent} an image" + ("" if sent == "sent" else f" from {data.sender}") + ", find it in {imgfilename}\n")
        img_bytes = binascii.unhexlify(data.message[9:])
        if not os.path.isdir(folder):
            os.mkdir(folder)
        imgfile = open(imgfilename, "wb")
        imgfile.write(img_bytes)

if __name__ == "__main__":
    try:
        db_host = sys.argv[1]
        lb_host = sys.argv[1] # can change to argv[2] for different devices
        client = Client(db_host, lb_host, 'fastchat_users')
        client.login()
        client.serve()
    except Exception as e: # any unhandled exception
        print(e)
        print(BLUE + "Client disconnected." + RESET)

