import sys
import socket
import select
import json
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from color_codes import *
import globals
from message import *

class Server:
    """Server class. Contains host address and port, 
    along with a connection to the PSQL server hosted locally.
    Contains a dictionary of Online users mapping to their MessageHandlers."""
    def __init__(self, host: str, port: str, database: str, index: str) -> None:
        """Constructor, initializes to a default IP and port. Creates empty databases."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.HOST = host  # The server's hostname or IP address
        self.PORT = int(port)  # The port used by the server
        self.index = index
        self.numClients = 0
        self.events = []
        self.userDBName = database
        self.onlineUserSockets: dict[str, MessageHandler] = {}

        self.databaseServer = psycopg2.connect(
            database=self.userDBName,
            host=self.HOST,
            user="postgres",
            password="password",
            port="5432"
        )
        self.sock.bind((self.HOST, self.PORT))
        self.sock.listen()
        self.sock.setblocking(True)
        print(f"Server #{int(self.index)} is operational!")
        print(f"Listening on {(self.HOST, self.PORT)}")

    def accept_connection(self):
        """Accepts the connection request from an authenticated client.
        Also accepts connections from other servers. Writes pending messages to the client."""
        conn, addr = self.sock.accept()  # ready to read
        conn.setblocking(True)
        s = MessageHandler(conn, addr)
        
        try:
                msg = s.read()
                if not msg:
                    return
                if type(msg)==dict:
                    username = msg['Username']
                else:
                    print("Error: ", type(msg), str(msg))
                    return
                
                if username[:7]=="Server ":
                    s.connectedTo = username
                    # serverindex = int(msg[7:])
                    self.onlineUserSockets[username] = s
                    print("Connecting to ", username, " from ", self.index)
                    print(list(self.onlineUserSockets.keys()))
                    conn.setblocking(True)
                    self.events.append(conn)
                    return

                print("Accepted connection from " + RED + str(addr) + RESET + " with username "  + GREEN + username + RESET)
                self.numClients += 1
                curs = self.databaseServer.cursor()
                curs.execute("""UPDATE serverload SET numclients=%s WHERE serverindex=%s""",(self.numClients, self.index))
                self.databaseServer.commit()
                curs.close()
                globals.Globals.Servers[int(self.index)][2] += 1
                print(globals.Globals.Servers[int(self.index)])
                self.onlineUserSockets[username] = s
                print("Connecting to ", username, " from ", self.index)
                self.events.append(conn)
                
                curs = self.databaseServer.cursor()
                curs.execute("SELECT msgid,jsonmsg,sendtime FROM pending WHERE receiver=%s ORDER BY sendtime",(username,))
                messages = curs.fetchall()
                self.onlineUserSockets[username].write(str(len(messages)))
                for mess in messages:
                    self.onlineUserSockets[username].write(mess)
                    curs.execute("DELETE FROM pending WHERE msgid=%s",(mess[0],))
                    self.databaseServer.commit()
                curs.close()

                print(username, list(self.onlineUserSockets.keys()))

        except Exception:
            print(f"Client " + GREEN + username + RESET + " closed the connection.")
            self.numClients -= 1
            curs = self.databaseServer.cursor()
            curs.execute("""UPDATE serverload SET numclients=%s WHERE serverindex=%s""",(self.numClients, self.index))
            self.databaseServer.commit()
            globals.Globals.Servers[int(self.index)][2] -= 1
            self.onlineUserSockets.pop(username)
            curs.execute("""UPDATE usercreds SET connectedto = -1 WHERE username=%s""", (username,))
            self.databaseServer.commit()
            curs.close()
            return

    def serve_client(self, readable_sock):
        """
        Main serve loop, monitors client connections.
        """
        username = None
        for user in self.onlineUserSockets:
            if self.onlineUserSockets[user].sock == readable_sock:
                username = user
                break
        try:
            
            msg = self.onlineUserSockets[username].read()
            if msg:
                msg_str = json.dumps(msg)
                # data.outb += recv_data
                curs = self.databaseServer.cursor()
                curs.execute("SELECT * FROM \"usercreds\" WHERE username=%s",(msg['Recipient'],))
                userentry = curs.fetchall()
                if msg['Recipient'] not in self.onlineUserSockets:
                    if userentry[0][5]==-1:
                        curs.execute("INSERT INTO pending (sender,receiver,jsonmsg) VALUES (%s,%s,%s) ",(msg['Sender'],msg['Recipient'],msg_str))
                        self.databaseServer.commit()
                    else:
                        self.onlineUserSockets["Server " + str(userentry[0][5])].write(msg)
                        
                else: # user is online and in the same server
                    self.onlineUserSockets[msg['Recipient']].write(msg)
                
                curs.close()
                # give acknowledgement of received to the sender
                # if username[7:] != 'Server ': 
                #     self.onlineUserSockets[username].write("received")
                # print(f"Client {data.username} to {msg['Recipient']}:", msg['Message'])
            
            # else the read returned nothing - the client did not try to send anything
            else:
                print("Closing connection from address " + RED + str(self.onlineUserSockets[username].addr) + RESET + ", username " + GREEN + username + RESET)
                assert(readable_sock != self.sock)
                self.events.remove(readable_sock)
                if username[:7]=="Server ":
                    self.serverConnections[int(username[7:])]=None
                else:
                    self.numClients -= 1
                    curs = self.databaseServer.cursor()
                    curs.execute("""UPDATE serverload SET numclients=%s WHERE serverindex=%s""",(self.numClients, self.index))
                    self.databaseServer.commit()
                    globals.Globals.Servers[int(self.index)][2] -= 1
                    self.onlineUserSockets.pop(username)
                    curs.execute("""UPDATE usercreds SET connectedto = -1 WHERE username=%s""", (username,))
                    self.databaseServer.commit()
                    curs.close()
        except Exception as e:
            print(e)
            print(f"Client " + GREEN + username + RESET + " closed the connection.")
            self.events.remove(readable_sock)
            self.numClients -= 1
            curs = self.databaseServer.cursor()
            curs.execute("""UPDATE serverload SET numclients=%s WHERE serverindex=%s""",(self.numClients, self.index))
            self.databaseServer.commit()
            globals.Globals.Servers[int(self.index)][2] -= 1
            self.onlineUserSockets.pop(username)
            curs.execute("""UPDATE usercreds SET connectedto = -1 WHERE username=%s""", (username,))
            self.databaseServer.commit()
            curs.close()
            return

    def run(self):
        """Main run function, calls the main serve loop"""
        self.sock.setblocking(True)
        self.events.append(self.sock)

        try:
            while True:
                readable_socks, _, _ = select.select(self.events, [], [])
                for readable_sock in readable_socks:
                    # print(key.data)
                    if readable_sock == self.sock: 
                        self.accept_connection()
                    else:
                        self.serve_client(readable_sock)
        except KeyboardInterrupt:
            print("Caught keyboard interrupt, exiting")
        
    def makeKn(self):
        """Connects each server to previously created servers, thus creating a fully connected server graph"""
        for i in range(0,int(self.index)):
            s = "Server " + str(i)
            s2 = "Server " + str(self.index)
            temp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            temp_sock.connect((globals.Globals.Servers[i][0],int(globals.Globals.Servers[i][1])))
            self.onlineUserSockets[s] = MessageHandler(temp_sock, (globals.Globals.Servers[i][0],int(globals.Globals.Servers[i][1])),s)
            print("Sending request to ", i, " from ", self.index)
            self.onlineUserSockets[s].write({"Username": s2})
            self.events.append(self.onlineUserSockets[s].sock)
            
    def num_active_clients(self):
        return self.numClients

if __name__ == '__main__':
    try:
        server = Server(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
        server.makeKn()
        server.run()
    except Exception as e:
        print(e)
        print(BLUE + "Server disconnected." + RESET)


