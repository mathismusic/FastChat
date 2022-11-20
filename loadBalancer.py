from server import Server

class LoadBalancer:
    def __init__(self, *servers, algorithm='least-load') -> None:
        self.servers = list(servers)
        self.algorithm = algorithm
    
    def accept_client(self):
        """Accepts the connection request from a client, after correct authentication.
        Creates a new account on corresponding request."""
        conn, addr = self.sock.accept()  # Should be ready to read
        msg = conn.recv(1024).decode()
        user_credentials: dict = json.loads(msg)
        username = user_credentials['Username']
        password = user_credentials['Password']
        newuser = user_credentials['Newuser']
          
        # TODO :- this block needs to be changed 
        if newuser:
            if username in users.keys():
                conn.sendall("invalid".encode())
                # conn.close()
                print("yes1")
                return
            else:
                users[username] = password # add user.
        elif (username not in users.keys() or password != users[username]):
            conn.sendall("invalid".encode())
            # conn.close()
            print("yes2")
            return

        print("Accepted connection from " + RED + str(addr) + RESET + " with username "  + GREEN + username + RESET)
        self.numClients += 1
        
        curs = self.databaseServer.cursor()
        curs.execute("INSERT INTO \"usercreds\" (username, userpwd) VALUES (%s,%s)",(username,password))
        curs.close()
        
        onlineUserSockets[username] = conn # change to bool = True
        conn.sendall('valid'.encode())
        conn.setblocking(False)
        data = SimpleNamespace(username=username, addr=addr, inb=b"", outb=b"")
        events = EVENT_READ | EVENT_WRITE
        self.selector.register(conn, events, data=data)