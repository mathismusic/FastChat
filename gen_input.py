num_clients = 100

for i in range(num_clients):
    f = open("testbench/input"+str(i), "w+")
    f.write("-1\n" + str(i) + "\npassword\n")
    for j in range(3):
        for k in range(num_clients - 1):
            to = k if k < i else k+1
            f.write(str(to)+"\nall\n"+"m1_"+str(i)+"_"+str(to)+"\n")
            f.write("m2_"+str(i)+"_"+str(to)+"\n")
            f.write("-cd\n")


