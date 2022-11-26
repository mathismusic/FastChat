import subprocess

num_clients = 100

for i in range(num_clients):
    subprocess.call(['python3 client.py < testbench/input' + str(i)])
