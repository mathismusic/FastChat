from pwnlib.tubes import process

num_clients = 100
ip = "192.168.103.215"
clients = []


for i in range(num_clients):
    clients.append(process(f'python client.py {ip}'))


for i in range(num_clients):
    clients[i].sendline()
