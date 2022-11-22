from server import Server
from loadBalancer import LoadBalancer
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

class System:
    def __init__(self, n: int = 1) -> None:
        self.HOST = '192.168.103.215' # where this is running.
        self.SERVER_HOSTS = ['192.168.103.215']*n
        self.SERVER_PORTS = [i for i in range(61001, 61001 + n)]
        self.LB_HOST = '192.168.103.215'
        self.LB_PORT = 61001 + 10*n

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
                        userpubkey TEXT NOT NULL
                    );""") # isonline INTEGER DEFAULT 1
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

        # initialize servers and load balancer
        self.servers = [Server()]*n
        self.loadBalancer = LoadBalancer(servers=self.servers, host=self.LB_HOST, port=self.LB_PORT, database=self.userDBName, algorithm='least-load')

if __name__ == '__main__':
    n = 2
    System(n)