from pwnlib.tubes import process

num_clients = 100
num_msgs = 2
ip = "192.168.103.215"
clients = []


for i in range(num_clients):
    clients.append(process(f'python client.py {ip}'))


for i in range(num_clients):
    clients[i].sendline('-1')
    clients[i].sendline(f'user{i}')
    clients[i].sendline('pwd')

for j in range(num_clients - 1):
    for i in range(num_clients):
        if j < i:
            clients[i].sendline(f'user{j}')
            clients[i].sendline('all')
            clients[i].sendline(f'm1_user{i}_user{j}')
            clients[i].sendline(f'm2_user{i}_user{j}')
            clients[i].sendline('-cd')
        else:
            clients[i].sendline(f'user{j+1}')
            clients[i].sendline('all')
            clients[i].sendline(f'm1_user{i}_user{j+1}')
            clients[i].sendline(f'm2_user{i}_user{j+1}')
            clients[i].sendline('-cd')

