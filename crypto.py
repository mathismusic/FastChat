from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric import rsa as RSA
import cryptography.hazmat.primitives.serialization as serial
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from message import Message
import binascii
import base64
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

class Crypt:
    """
    The cryptography handler class. Requires the cryptography module. Handles key generation, 
    data encryption-decryption, and password hashing.
    """
    def __init__(self):
        """
        Constructor
        """
        self.RSA_priv_decrypt_key = None
        self.RSA_pub_decrypt_key = None
        self.RSA_encrypt_key = None
        self.fernet_encrypt_key = None
    
    # rsa stuff
    def gen_rsa_key(self) -> RSA.RSAPrivateKey:
        """
        Generates a fresh new RSA private token, and returns a RSA.RSAPrivateKey object

        :rtype: RSA.RSAPrivateKey
        :return: The RSAPrivateKey attribute
        """
        self.RSA_priv_decrypt_key = RSA.generate_private_key(public_exponent= 65537, key_size=2048,backend=default_backend())
        self.RSA_pub_decrypt_key = self.RSA_priv_decrypt_key.public_key()
        return self.RSA_priv_decrypt_key

    #decrypt key from server
    def set_priv_key(self, password, encypted_bytes) -> RSA.RSAPrivateKey:
        """
        Loads the RSA key from it's serialized bytes. The keys are encrypted with the password.

        :param: password: The password
        :type: password: str
        :param: encrypted_bytes: The encrypted byte string of the password
        :type: encrypted_bytes: bytes
        :rtype: RSA.RSAPrivateKey
        :return: The RSAPrivateKey attribute
        """
        self.RSA_priv_decrypt_key = serial.load_pem_private_key(encypted_bytes, password.encode(), default_backend())
        self.RSA_pub_decrypt_key = self.RSA_priv_decrypt_key.public_key()
        return self.RSA_priv_decrypt_key

    #get the encrypted byte string of the private key, to be stored on (private) database
    def get_rsa_private_str(self, password) -> bytes:
        """
        Encrypts the private key with the password.

        :param: password: The password
        :rtype: bytes
        :returns: The encrypted RSA key bytes
        """
        return self.RSA_priv_decrypt_key.private_bytes(
        serial.Encoding.PEM,
        serial.PrivateFormat.PKCS8,
        serial.BestAvailableEncryption(password.encode())
        )

    #get the unencrypted byte string of the public key, to be stored on public database
    def get_rsa_public_str(self) -> bytes:
        """
        Generates the unecrypted public key byte string.

        :return: The unencrypted byte string
        :rtype: bytes
        """
        return self.RSA_pub_decrypt_key.public_bytes(serial.Encoding.PEM, serial.PublicFormat.SubjectPublicKeyInfo)
    
    # get the RSA_encryption_key (public), from the server
    def get_rsa_encrypt_key(self, public_bytes) -> RSA.RSAPublicKey:
        """
        Gets the RSA encryption key(public) from its bytes obtained from the server database.

        :param: public_bytes: The public key bytes
        :type: public_bytes: bytes
        :rtype: RSA.RSAPublicKey
        :return: The RSA.RSAPublicKey attribute
        """
        self.RSA_encrypt_key = serial.load_pem_public_key(public_bytes, default_backend())
        return self.RSA_encrypt_key

    #fernet stuff
    # generate a fernet key, and return an encrypted version of it
    def gen_fernet_encrypt_key(self) -> bytes:
        """
        Generate and set a Fernet key, and return its RSA encrypted version

        :rtype: bytes
        :return: Fernet key
        """
        self.fernet_encrypt_key = Fernet.generate_key()

        return self.RSA_encrypt_key.encrypt(
        self.fernet_encrypt_key, 
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
            )
        )

    def fernet_encrypt_message(self, message) -> str:
        """
        Encrypt the message with the Fernet key

        :param: message
        :type: message: str
        :rtype: str
        :return: Fernet encrypted message
        """
        f = Fernet(self.fernet_encrypt_key)
        return f.encrypt(message.encode()).decode()

    def fernet_decrypt_message(self, cipher, fernet_decrypt_key) -> str:
        """
        Decrypt the message with the Fernet key

        :param: cipher
        :type: message: str
        :param: fernet_decrypt_key: The Fernet decryption key
        :type: fernet_decrypt_key: str
        :rtype: str
        :return: Fernet decrypted message
        """
        f = Fernet(fernet_decrypt_key)
        return f.decrypt(cipher.encode() ).decode()

    #get fernet key from its encrypted version
    def decrypt_fernet_key(self, encrypted_fernet_key) -> bytes:
        """
        Decrypt the Fernet key using the RSA key

        :param: encrypted_fernet_key: The encrypted Fernet key bytes
        :type: encrypted_fernet_key: bytes
        """
        return self.RSA_priv_decrypt_key.decrypt(encrypted_fernet_key, 
            padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
            )
        )

    # return encrypted message, public encrypt key must be set BEFORE this
    def main_encrypt(self, message_obj : Message) -> Message:
        """
        Encrypt the main message, with a newly generated fernet key which is assigned to the message
        after RSA encryption. RSA encrypt key must be set before this is called.

        :param: message_obj: The message
        :type: message_obj: Message
        :rtype: Message
        :return: The encrypted message object
        """
        encrypted = Message(message_obj.sender, message_obj.recipient, message_obj.message, message_obj.fernet_key, message_obj.group_name)
        encrypted.fernet_key = binascii.hexlify(self.gen_fernet_encrypt_key()).decode()
        encrypted.message = self.fernet_encrypt_message(message_obj.message)
        return encrypted

    #decrypt message, private key must be set BEFORE this
    def main_decrypt(self, message_obj : Message) -> Message:
        """
        Decrypt the main message, by decrypting its Fernet key with the RSA private key and then the 
        message with the Fernet. RSA private key must be set before this is called. 

        :param: message_obj: The message
        :type: message_obj: Message
        :rtype: Message
        :return: The encrypted message object        
        """
        decrypted = Message(message_obj.sender, message_obj.recipient, message_obj.message, message_obj.fernet_key, message_obj.group_name)
        decrypted.fernet_key = self.decrypt_fernet_key(binascii.unhexlify(message_obj.fernet_key.encode())).decode()
        decrypted.message = self.fernet_decrypt_message(message_obj.message, decrypted.fernet_key.encode())
        return decrypted

    def hash_string(self, password : str) ->str :
        """
        SHA256 hash with hex encoding.

        :param: password: The password
        :type: password: str
        :rtype: str
        :return: The hashed password
        """
        digest = hashes.Hash(hashes.SHA256(), default_backend())
        digest.update(password.encode())
        b = digest.finalize()
        return binascii.hexlify(b).decode()

    # password encryption, salt = b""
    def password_encrypt(self, password: str, message_obj : Message) -> Message:
        """
        Encrypt the message with password.

        :param: message_obj: the message
        :type: message_obj: Message
        :param: password
        :type: password: str
        :rtype: Message
        :return: The encrypted message
        """
        pwd_bytes = password.encode()
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"",
            iterations=390000,
            backend = default_backend()
        )
        key = base64.urlsafe_b64encode(kdf.derive(pwd_bytes))
        f = Fernet(key)
        pwd_encrypted_msg = Message(message_obj.sender, message_obj.recipient, message_obj.message, message_obj.fernet_key, message_obj.group_name)
        pwd_encrypted_msg.message = f.encrypt(message_obj.message.encode()).decode()
        pwd_encrypted_msg.fernet_key = f.encrypt(message_obj.fernet_key.encode()).decode()
        return pwd_encrypted_msg

    def password_decrypt(self, password : str, message_obj : Message) -> Message:
        """
        Decrypt the message with password.

        :param: message_obj: the message
        :type: message_obj: Message
        :param: password
        :type: password: str
        :rtype: Message
        :return: The decrypted message
        """
        pwd_bytes = password.encode()
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"",
            iterations=390000,
            backend = default_backend()
        )
        key = base64.urlsafe_b64encode(kdf.derive(pwd_bytes))
        f = Fernet(key)

        pwd_decrypted_msg = Message(message_obj.sender, message_obj.recipient, message_obj.message, message_obj.fernet_key, message_obj.group_name)
        pwd_decrypted_msg.message = f.decrypt(message_obj.message.encode()).decode()
        pwd_decrypted_msg.fernet_key = f.decrypt(message_obj.fernet_key.encode()).decode()
        return pwd_decrypted_msg





    
    