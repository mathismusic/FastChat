import sys
import json
import io
import struct

class Message:
    """
    This is the standard format of all messages transferred between servers and clients.
    It is in standard JSON format with attributes Sender, Recipient and Message
    """
    def __init__(self, sender, rec, msg, key, grp_name =  None) -> None:
        self.sender =  sender
        self.recipient = rec
        self.message = msg
        self.fernet_key = key
        self.group_name = grp_name
    
    def get_json(self):
        return {"Sender": self.sender, "Recipient": self.recipient, "Message": self.message, "Key": self.fernet_key, "Group_Name": self.group_name }

    def __repr__(self) -> str:
        return json.dumps({"Sender": self.sender, "Recipient": self.recipient, "Message": self.message, "Key": self.fernet_key, "Group_Name": self.group_name })

class ServerMessageHandler:
    def __init__(self,sock, addr,connectedTo="_default"):
        self.connectedTo = connectedTo
        self.sock = sock
        self.addr = addr
        self._recv_buffer = b""
        self._send_buffer = b""
        self._jsonheader_len = None
        self.jsonheader = None
        self.request = None
        self.requests = []

    # def _set_selector_events_mask(self, mode):
    #     """Set selector to listen for events: mode is 'r', 'w', or 'rw'."""
    #     if mode == "r":
    #         events = selectors.EVENT_READ
    #     elif mode == "w":
    #         events = selectors.EVENT_WRITE
    #     elif mode == "rw":
    #         events = selectors.EVENT_READ | selectors.EVENT_WRITE
    #     else:
    #         raise ValueError(f"Invalid events mask mode {mode!r}.")
    #     self.selector.modify(self.sock, events, data=self)

    def _read(self):
        try:
            # Should be ready to read
            data = self.sock.recv(4096)
            print("r")
        except BlockingIOError:
            # Resource temporarily unavailable (errno EWOULDBLOCK)
            pass
        else:
            if data:
                self._recv_buffer += data
            else:
                raise RuntimeError("Peer closed.")

    def _write(self):
        if self._send_buffer:
            #print(f"Sending {self._send_buffer!r} to {self.addr}")
            try:
                # Should be ready to write
                sent = self.sock.send(self._send_buffer)
            except BlockingIOError:
                # Resource temporarily unavailable (errno EWOULDBLOCK)
                pass
            else:
                self._send_buffer = self._send_buffer[sent:]
                # Close when the buffer is drained. The response has been sent.
                if sent and not self._send_buffer:
                    #self.close()
                    pass

    def _json_encode(self, obj, encoding):
        return json.dumps(obj, ensure_ascii=False).encode(encoding)

    def _json_decode(self, json_bytes, encoding):
        tiow = io.TextIOWrapper(
            io.BytesIO(json_bytes), encoding=encoding, newline=""
        )
        obj = json.load(tiow)
        tiow.close()
        return obj

    def _create_message(
        self, *, content_bytes, content_type, content_encoding
    ):
        jsonheader = {
            "byteorder": sys.byteorder,
            "content-type": content_type,
            "content-encoding": content_encoding,
            "content-length": len(content_bytes),
        }
        jsonheader_bytes = self._json_encode(jsonheader, "utf-8")
        message_hdr = struct.pack(">H", len(jsonheader_bytes))
        message = message_hdr + jsonheader_bytes + content_bytes
        return message

    def _create_response_json_content(self):
        content_encoding = "utf-8"
        response = {
            "content_bytes": self._json_encode(self.request, content_encoding),
            "content_type": "text/json",
            "content_encoding": content_encoding,
        }
        return response

    # def _create_response_binary_content(self):
    #     response = {
    #         "content_bytes": b"First 10 bytes of request: "
    #         + self.request[:10],
    #         "content_type": "binary/custom-server-binary-type",
    #         "content_encoding": "binary",
    #     }
    #     return response        
        

    def read(self):
        while True:
            self._read()
            if self._recv_buffer == "":
                return ""
            if self._jsonheader_len is None:
                self.process_protoheader()
            if self._jsonheader_len is not None:
                if self.jsonheader is None:
                    self.process_jsonheader()
                    msg = self.process_request()
                    if msg != "":
                        self._jsonheader_len = None
                        self.jsonheader = None
                        self.request = None
                        return msg

    def write(self, msg):
        self.requests.append(msg)
        self.request = self.requests.pop(0)
        if self.request:
            self.create_response()

        self._write()
        self._jsonheader_len = None
        self.jsonheader = None
        self.request = None

    def close(self):
        print(f"Closing connection to {self.addr}")
        try:
            self.selector.unregister(self.sock)
        except Exception as e:
            print(
                f"Error: selector.unregister() exception for "
                f"{self.addr}: {e!r}"
            )

        try:
            self.sock.close()
        except OSError as e:
            print(f"Error: socket.close() exception for {self.addr}: {e!r}")
        finally:
            # Delete reference to socket object for garbage collection
            self.sock = None

    def process_protoheader(self):
        hdrlen = 2
        if len(self._recv_buffer) >= hdrlen:
            self._jsonheader_len = struct.unpack(
                ">H", self._recv_buffer[:hdrlen]
            )[0]
            self._recv_buffer = self._recv_buffer[hdrlen:]

    def process_jsonheader(self):
        hdrlen = self._jsonheader_len
        if len(self._recv_buffer) >= hdrlen:
            self.jsonheader = self._json_decode(
                self._recv_buffer[:hdrlen], "utf-8"
            )
            self._recv_buffer = self._recv_buffer[hdrlen:]
            for reqhdr in (
                "byteorder",
                "content-length",
                "content-type",
                "content-encoding",
            ):
                if reqhdr not in self.jsonheader:
                    raise ValueError(f"Missing required header '{reqhdr}'.")

    def process_request(self):
        content_len = self.jsonheader["content-length"]
        if not len(self._recv_buffer) >= content_len:
            return ""
        data = self._recv_buffer[:content_len]
        self._recv_buffer = self._recv_buffer[content_len:]
        if self.jsonheader["content-type"] == "text/json":
            encoding = self.jsonheader["content-encoding"]
            msg = self._json_decode(data, encoding)
            return msg
            # curs = self.databaseServer.cursor()
            # curs.execute("SELECT * FROM \"usercreds\" WHERE username=%s",(msg['Recipient'],))
            # userentry = curs.fetchall()
            # if len(userentry)==0:
            #     self.requests.("invalid Recipient")
            #     return
            # elif msg['Recipient'] not in onlineUsers:
            #     if userentry[0][5]==-1:
            #         curs.execute(" INTO pending (sender,receiver,jsonmsg) VALUES (%s,%s,%s) ",(msg['Sender'],msg['Recipient'],msg))
            #         self.databaseServer.commit()
            #     else:
            #         self.serverConnections[userentry[0][5]].sendall(recv_data)
                    
            # else: # user is online and in the same server
            #     self.onlineUserSockets[msg['Recipient']].sendall(recv_data)
            # curs.close()
            
            #print(f"Received request {self.request!r} from {self.addr}")
        #else:
            # Binary or unknown content-type
            #self.request = data
            # print(
            #     f"Received {self.jsonheader['content-type']} "
            #     f"request from {self.addr}"
            # )
        # Set selector to listen for write events, we're done reading.
        # self._set_selector_events_mask("w")

    def create_response(self):
        response = self._create_response_json_content()
        message = self._create_message(**response)
        self._send_buffer += message