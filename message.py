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
        """
        Returns a dictionary containing the details of the message

        :rtype: dict[str, str]  
        """
        return {"Sender": self.sender, "Recipient": self.recipient, "Message": self.message, "Key": self.fernet_key, "Group_Name": self.group_name }

    def __repr__(self) -> str:
        return json.dumps({"Sender": self.sender, "Recipient": self.recipient, "Message": self.message, "Key": self.fernet_key, "Group_Name": self.group_name }, default=str)

class MessageHandler:
    """
    The message protocol class providing functionalities to send and receive messages
    """
    def __init__(self,sock, addr,connectedTo="_default"):
        """
        Constructor, Initializes the connection socket to send and receive messages along with buffers
        """
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
        """
        Helper method to receive bytes from the connected device to the receive_buffer
        """
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
        """
        Helper method to send bytes from send_buffer to connected device
        """
        if self._send_buffer:
            try:
                # Should be ready to write
                sent = self.sock.send(self._send_buffer)
            except Exception as e:
                print(e)
            else:
                self._send_buffer = self._send_buffer[sent:]
                
    def _json_encode(self, obj, encoding):
        """
        Helper method to byte encode the given object using given
encoding protocol

        :param: obj: the object to be encoded

        :param: encoding: name of the encoding protocol
        :type: encoding str         """
        return json.dumps(obj, ensure_ascii=False, default=str).encode(encoding)

    def _json_decode(self, json_bytes, encoding):
        """
        Helper method to decode byte string provided the encoding protocol

        :param: json_bytes: the byte object to be decoded

        :param: encoding: name of the encoding protocol
        :type: encoding str
        """
        tiow = io.TextIOWrapper(
            io.BytesIO(json_bytes), encoding=encoding, newline=""
        )
        obj = json.load(tiow)
        tiow.close()
        return obj

    def _create_message(
        self, content_bytes, content_type, content_encoding
    ):
        """
        Helper method to generate the message to be sent, given the content bytes and types of encoding
        """
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
        """
        Method to create Message protocol json content 
        """
        content_encoding = "utf-8"
        response = {
            "content_bytes": self._json_encode(self.request, content_encoding),
            "content_type": "text/json",
            "content_encoding": content_encoding
        }
        return response

    def read(self,tag=False):
        """
        Receives byte message and decode it to get the message

        :param: tag: To specify whether to read from buffer or read a new message
        :type: tag: bool        
        :return: the decoded message
        """
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

        """
        Sends the message to the connected device according to the Message protocol encoding and formatting

        :param: msg: message to be sent
        """        
        self.requests.append(msg)
        self.request = self.requests.pop(0)
        if self.request:
            self.create_response()

        self._write()
        self.request = None

    def process_protoheader(self):

        """
        Processes the first part of the received message
        """        
        hdrlen = 2
        if len(self._recv_buffer) >= hdrlen:
            self._jsonheader_len = struct.unpack(
                ">h", self._recv_buffer[:hdrlen]
            )[0]
            self._recv_buffer = self._recv_buffer[hdrlen:]

    def process_jsonheader(self):

        """
        Processes the second part of the received message
        """        
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

        """
        Processes the third part of the received message i.e. the actual message content
        """        
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

        """
        Creates a response message to be send and adding it to the send_buffer
        """        
        response = self._create_response_json_content()
        message = self._create_message(response["content_bytes"], response["content_type"], response["content_encoding"])
        self._send_buffer += message