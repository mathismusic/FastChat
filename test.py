import subprocess

num_clients = 100

for i in range(num_clients):
    subprocess.Popen(['python client2.py < testbench/input' + str(i)])
