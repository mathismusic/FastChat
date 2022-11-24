import json

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
    
    def __repr__(self) -> str:
        return json.dumps({"Sender": self.sender, "Recipient": self.recipient, "Message": self.message, "Key": self.fernet_key, "Group_Name": self.group_name })
