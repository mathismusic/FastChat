from pwnlib.tubes.process import process
from time import sleep, time

num_clients = 10
num_msgs = 2
ip = "192.168.103.215"
clients = []
sleep_buffer = 0.1

for i in range(num_clients):
    clients.append(process(f'python client_test.py {ip}', shell=True))

print(clients)


for i in range(num_clients):
    clients[i].sendline(f'-1'.encode())

    clients[i].sendline(f'user11{i}'.encode())

    clients[i].sendline('pwd'.encode())
    sleep(1)
    # print(clients[i].recv())

start = time()
for j in range(num_clients-1):
    for i in range(num_clients):
        if j < i:
            clients[i].sendline(f'user11{j}'.encode())
            sleep(sleep_buffer)
            clients[i].sendline('quick'.encode())
            sleep(sleep_buffer)
            clients[i].sendline(f'm1_user{i}_user{j}'.encode())
            sleep(sleep_buffer)
            clients[i].sendline(f'm2_user{i}_user{j}'.encode())
            sleep(sleep_buffer)
            clients[i].sendline('-cd'.encode())
            sleep(sleep_buffer)
            # print(clients[i].recv())
        else:
            clients[i].sendline(f'user11{j+1}'.encode())
            sleep(sleep_buffer)
            clients[i].sendline('quick'.encode())
            sleep(sleep_buffer)
            clients[i].sendline(f'm1_user{i}_user{j+1}'.encode())
            sleep(sleep_buffer)
            clients[i].sendline(f'm2_user{i}_user{j+1}'.encode())
            sleep(sleep_buffer)
            clients[i].sendline('-cd'.encode())
            sleep(sleep_buffer)
            # print(clients[i].recv())

for i in range(num_clients):
    clients[i].sendline(f'user11{(i+1)%num_clients}'.encode())
    sleep(sleep_buffer)

for i in range(num_clients):
    clients[i].sendline('-e'.encode())

end = time()
print(end - start)