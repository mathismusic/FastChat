# echo-server.py

import socket,sys,selectors, types

HOST = "192.168.103.215"  # Standard loopback interface address (localhost)
PORT = 5001  # Port to listen on (non-privileged ports are > 1023)

# sel = selectors.DefaultSelector()

# def accept_wrapper(sock):
#     conn, addr = sock.accept()
#     print(f"Connected by {addr}")
#     conn.setblocking(False)
#     data = types.SimpleNamespace(addr = addr, inb = b"", outb = b"")
#     events = selectors.EVENT_READ | selectors.EVENT_WRITE
#     sel.register(conn, events, data=data)
    
# def service_connection(key, mask):
#     sock = key.fileobj
#     data = key.data
#     if mask & selectors.EVENT_READ:
#         while True:
#             d = sock.recv(1024)
#             if not d or d=="exit":
#                 sel.unregister
#                 break
#             print(f"Received:", data.decode())
#             a = input("Client:")
#             conn.sendall(bytes(str(a).encode()))

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.bind((HOST, PORT))
    s.listen()
    conn, addr = s.accept()
    with conn:
        print(f"Connected by {addr}")
        while True:
            data = conn.recv(1024).decode()
            if data is None or data=="exit":
                break
            print("Received:", data)
            a = input("ToClient: ")
            if a == "": a = "Received."
            conn.sendall(bytes(str(a).encode()))