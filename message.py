import sys
import json
import io
import struct
import socket

class Message:
    """
    This is the standard format of all messages transferred between servers and clients.
    It is in standard JSON format with attributes Sender, Recipient, Message, Fernet_Key and Group_Name
    All messages on server side are encrypted.
    """
    def __init__(self, sender, rec, msg, key, grp_name =  None) -> None:
        self.sender: str =  sender
        self.recipient: str = rec
        self.message: str = msg
        self.fernet_key = key
        self.group_name: str = grp_name
    
    def get_json(self):
        return {"Sender": self.sender, "Recipient": self.recipient, "Message": self.message, "Key": self.fernet_key, "Group_Name": self.group_name }

    def __repr__(self) -> str:
        return json.dumps({"Sender": self.sender, "Recipient": self.recipient, "Message": self.message, "Key": self.fernet_key, "Group_Name": self.group_name }, default=str)

class ServerMessageHandler:
    """
    The message protocol 
    """
    def __init__(self,sock, addr,connectedTo="_default"):
        self.connectedTo = connectedTo
        self.sock: socket.socket = sock
        self.addr = addr
        self._recv_buffer = b""
        self._send_buffer = b""
        self._jsonheader_len = None
        self.jsonheader = None
        self.request = None
        self.requests = []

    def _read(self):
        try:
            # Should be ready to read
            data = self.sock.recv(4096)
        except Exception as e:
            print(e)
        else:
            if data != b'':
                self._recv_buffer += data
            else:
                raise RuntimeError("Peer closed.")

    def _write(self):
        if self._send_buffer:
            try:
                # Should be ready to write
                sent = self.sock.send(self._send_buffer)
            except Exception as e:
                print(e)
            else:
                self._send_buffer = self._send_buffer[sent:]
                
    def _json_encode(self, obj, encoding):
        return json.dumps(obj, ensure_ascii=False, default=str).encode(encoding)

    def _json_decode(self, json_bytes, encoding):
        tiow = io.TextIOWrapper(
            io.BytesIO(json_bytes), encoding=encoding, newline=""
        )
        obj = json.load(tiow)
        tiow.close()
        return obj

    def _create_message(
        self, content_bytes, content_type, content_encoding
    ):
        jsonheader = {
            "byteorder": sys.byteorder,
            "content-type": content_type,
            "content-encoding": content_encoding,
            "content-length": len(content_bytes),
        }
        jsonheader_bytes = self._json_encode(jsonheader, "utf-8")
        message_hdr = struct.pack(">h", len(jsonheader_bytes))
        message = message_hdr + jsonheader_bytes + content_bytes
        # print(message)
        return message

    def _create_response_json_content(self):
        content_encoding = "utf-8"
        response = {
            "content_bytes": self._json_encode(self.request, content_encoding),
            "content_type": "text/json",
            "content_encoding": content_encoding
        }
        return response

    def read(self,tag=False):
        try:
            if tag and self._recv_buffer:
                if self._jsonheader_len is None:
                    self.process_protoheader()

                if self._jsonheader_len is not None:
                    if self.jsonheader is None:
                        self.process_jsonheader()
                if self.jsonheader is not None:
                    msg = self.process_request()
                    if msg not in ["",None]:
                        self._jsonheader_len = None
                        self.jsonheader = None
                        self.request = None
                        return msg
            while True:
                self._read()
                if self._recv_buffer == b"":
                    return ""

                if self._jsonheader_len is None:
                    self.process_protoheader()

                if self._jsonheader_len is not None:
                    if self.jsonheader is None:
                        self.process_jsonheader()
                if self.jsonheader is not None:
                    msg = self.process_request()
                    if msg not in ["",None]:
                        self._jsonheader_len = None
                        self.jsonheader = None
                        self.request = None
                        return msg
        except Exception as e:
            print(e)

    def write(self, msg):
        self.requests.append(msg)
        self.request = self.requests.pop(0)
        if self.request:
            self.create_response()

        self._write()
        self.request = None

    def process_protoheader(self):
        hdrlen = 2
        if len(self._recv_buffer) >= hdrlen:
            self._jsonheader_len = struct.unpack(
                ">h", self._recv_buffer[:hdrlen]
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

    def create_response(self):
        response = self._create_response_json_content()
        message = self._create_message(response["content_bytes"], response["content_type"], response["content_encoding"])
        self._send_buffer += message