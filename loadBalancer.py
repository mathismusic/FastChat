import socket
import json
import psycopg2
from server import Server

# load balancer server
class LoadBalancer:
    def __init__(self, servers: list[Server], host: str, port: str, database: str, algorithm='least-load') -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.HOST = host  # The load balancer's hostname or IP address
        self.PORT = port  # The port used by the balancer
        self.servers = list(servers)
        self.userDBName = database
        self.algorithm = algorithm
        print(self.HOST)
    
    # the load balancer does the work of accepting clients when they try to login
    def accept_client(self):
        """Accepts the connection request from a client, after correct authentication.
        Creates a new account on corresponding request. The accepted client is connected to a chosen server"""
        
        conn, addr = self.sock.accept()  # Should be ready to read

        msg = conn.recv(1024).decode()
        user_credentials: dict = json.loads(msg)
        
        username = user_credentials['Username']
        password = user_credentials['Password']
        user_priv_key = user_credentials['Private_Key']
        user_pub_key = user_credentials['Public_Key']
        newuser = user_credentials['Newuser']

        databaseServer = psycopg2.connect(
            database=self.userDBName,
            host=self.HOST,
            user="postgres",
            password="password",
            port="5432"
        )
        curs = databaseServer.cursor()
        curs.execute("SELECT * FROM \"usercreds\" WHERE username=%s",(username,))
        data = curs.fetchall()
        if newuser:
            if len(data) > 0:
                conn.sendall("invalid".encode())
                print("yes1")
                return
            else:
                curs.execute("INSERT INTO \"usercreds\" (username,userpwd,userprivkey, userpubkey) VALUES (%s, %s, %s, %s)",(username,password, user_priv_key, user_pub_key)) # add user.
                databaseServer.commit()
        elif (len(data) == 0 or password != data[0][2]):
            conn.sendall("invalid".encode())
            # conn.close()
            print("yes2")
            return

        # connect the user to server
        server = self.choose_server()
        conn.sendall(json.dumps({"hostname": server.HOST, "port": server.PORT}).encode())
        # server.accept_client(conn, addr, username, password)

    def choose_server(self) -> Server:
        ans = self.servers[0]
        for server in self.servers:
            if server.num_active_clients() < ans.num_active_clients():
                ans = server
        return ans