import psycopg2
import json
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import subprocess
from globals import Globals

class System:
    """The overall server and load balancer initializer class. Creates the relevant databases."""
    def __init__(self, n: int) -> None:
        """
        Constructor, sets server and lb (load balancer) addresses.
        Creates the fastchat_users database with the usercreds table, groups table and pending
        message table with the required schema. Runs the shell script start_lb and start_server to run the programs automatically.
        """
        self.HOST = Globals.default_host # where this is running.
        self.SERVER_HOSTS = [Globals.default_host]*n
        self.SERVER_PORTS = [str(i) for i in range(61001, 61001 + n)]
        self.LB_HOST = Globals.default_host
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
                        connectedto INTEGER NOT NULL
                    );""") # isonline INTEGER DEFAULT 1
        curs.execute("ALTER TABLE usercreds ALTER COLUMN connectedto SET DEFAULT -1;")
        self.databaseServer.commit()
        curs.execute("""CREATE TABLE IF NOT EXISTS groups (
                            groupid SERIAL PRIMARY KEY,
                            groupname VARCHAR(256) NOT NULL,
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
        curs.execute("""CREATE TABLE IF NOT EXISTS serverload (
                        serverindex INTEGER PRIMARY KEY,
                        numclients INTEGER
                    );""")
        self.databaseServer.commit()
        curs.close()

        # initialize server data and load balancer data
        self.servers = [[self.SERVER_HOSTS[i], self.SERVER_PORTS[i], self.userDBName] for i in range(n)]
        for i in range(n):
            subprocess.call(['./start_server.sh', self.SERVER_HOSTS[i], self.SERVER_PORTS[i], self.userDBName, str(i)])
            curs = self.databaseServer.cursor()
            curs.execute("""INSERT INTO serverload (serverindex, numclients) VALUES (%s,%s) """, (i, 0))
            self.databaseServer.commit()
            curs.close()
        self.loadBalancer = [self.servers, self.LB_HOST, self.LB_PORT, self.userDBName, 'least-load']
        subprocess.call(['./start_lb.sh', json.dumps(self.loadBalancer)])

if __name__ == '__main__':
    n = 3
    System(n)