from server import Server
from loadBalancer import LoadBalancer
import psycopg2
import json
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import threading
import subprocess

class System:
    def __init__(self, n: int) -> None:
        self.HOST = '192.168.103.215' # where this is running.
        self.SERVER_HOSTS = ['192.168.103.215']*n
        self.SERVER_PORTS = [str(i) for i in range(61001, 61001 + n)]
        self.LB_HOST = '192.168.103.215'
        self.LB_PORT = str(61001 + 10*n)

        # create database. Since this is the first time FastChat opens, any old databases with the same name will be deleted if exists
        self.userDBName = "fastchat_users" # name of the psql database to store user details

        self.databaseServer = psycopg2.connect(
            host=self.HOST,
            user="postgres",
            password="password",
            port="5432"
        )
        self.databaseServer.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        curs = self.databaseServer.cursor()
        curs.execute("DROP DATABASE IF EXISTS " + self.userDBName)
        curs.execute("CREATE DATABASE " + self.userDBName)
        
        self.databaseServer.commit()
        curs.close()

        self.databaseServer = psycopg2.connect(
            database=self.userDBName,
            host=self.HOST,
            user="postgres",
            password="password",
            port="5432"
        )

        curs = self.databaseServer.cursor()
        curs.execute("""CREATE TABLE IF NOT EXISTS usercreds (
                        userid SERIAL PRIMARY KEY,
                        username VARCHAR(256) NOT NULL,
                        userpwd VARCHAR(256) NOT NULL,
                        userprivkey TEXT NOT NULL,
                        userpubkey TEXT NOT NULL,
                        connectedto INTEGER NOT NULL DEFAULT -1
                    );""") # isonline INTEGER DEFAULT 1
        curs.execute("""CREATE TABLE IF NOT EXISTS groups (
                            groupid SERIAL PRIMARY KEY,
                            groupname TEXT NOT NULL,
                            groupmembers TEXT NOT NULL,
                            adminlist TEXT NOT NULL
                    );""")
        self.databaseServer.commit()
        curs.execute("""CREATE TABLE IF NOT EXISTS pending (
                        msgid SERIAL NOT NULL PRIMARY KEY,
                        sender VARCHAR(256) NOT NULL,
                        receiver VARCHAR(256) NOT NULL,
                        jsonmsg TEXT NOT NULL,
                        sendtime TIMESTAMP NOT NULL
                    );""")
        curs.execute("ALTER TABLE pending ALTER COLUMN sendtime SET DEFAULT now();")
        self.databaseServer.commit()
        curs.close()

        # initialize server data and load balancer data
        self.servers = [[self.SERVER_HOSTS[i], self.SERVER_PORTS[i], self.userDBName] for i in range(n)]
        for i in range(n):
            # pass
            subprocess.call(['./start_server.sh', self.SERVER_HOSTS[i], self.SERVER_PORTS[i], self.userDBName, str(i+1)])
        # print("hello worlddd")
        self.loadBalancer = [self.servers, self.LB_HOST, self.LB_PORT, self.userDBName, 'least-load']
        # print(json.dumps(self.loadBalancer))
        subprocess.call(['./start_lb.sh', json.dumps(self.loadBalancer)])

        # threads: list[threading.Thread] = []
        # for i in range(n):
        #     threads.append(threading.Thread(target=self.servers[i].run, args=tuple()))
        #     threads[-1].start()

if __name__ == '__main__':
    n = 1
    System(n)