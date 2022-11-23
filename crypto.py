from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric import rsa as RSA
import cryptography.hazmat.primitives.serialization as serial
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from message import Message
import binascii

class Crypt:

    def __init__(self):
        self.RSA_priv_decrypt_key = None
        self.RSA_pub_decrypt_key = None
        self.RSA_encrypt_key = None
        self.fernet_encrypt_key = None
    
    # rsa stuff
    def gen_rsa_key(self) -> RSA.RSAPrivateKey:
        self.RSA_priv_decrypt_key = RSA.generate_private_key(public_exponent= 65537, key_size=2048,backend=default_backend())
        self.RSA_pub_decrypt_key = self.RSA_priv_decrypt_key.public_key()
        return self.RSA_priv_decrypt_key

    #decrypt key from server
    def set_priv_key(self, password, encypted_bytes) -> RSA.RSAPrivateKey:
        self.RSA_priv_decrypt_key = serial.load_pem_private_key(encypted_bytes, password.encode(), default_backend())
        self.RSA_pub_decrypt_key = self.RSA_priv_decrypt_key.public_key()
        return self.RSA_priv_decrypt_key

    #get the encrypted byte string of the private key, to be stored on (private) database
    def get_rsa_private_str(self, password) -> bytes:
        return self.RSA_priv_decrypt_key.private_bytes(
        serial.Encoding.PEM,
        serial.PrivateFormat.PKCS8,
        serial.BestAvailableEncryption(password.encode())
        )

    #get the unencrypted byte string of the public key, to be stored on public database
    def get_rsa_public_str(self) -> bytes:
        return self.RSA_pub_decrypt_key.public_bytes(serial.Encoding.PEM, serial.PublicFormat.SubjectPublicKeyInfo)
    
    # get the RSA_encryption_key (public), from the server
    def get_rsa_encrypt_key(self, public_bytes) -> RSA.RSAPublicKey:
        self.RSA_encrypt_key = serial.load_pem_public_key(public_bytes, default_backend())
        return self.RSA_encrypt_key

    #fernet stuff
    # generate a fernet key, and return an encrypted version of it
    def gen_fernet_encrypt_key(self) -> bytes:
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
        f = Fernet(self.fernet_encrypt_key)
        return f.encrypt(message.encode()).decode()

    def fernet_decrypt_message(self, cipher, fernet_decrypt_key) -> str:
        f = Fernet(fernet_decrypt_key)
        return f.decrypt(cipher.encode() ).decode()

    #get fernet key from its encrypted version
    def decrypt_fernet_key(self, encrypted_fernet_key) -> bytes:
        return self.RSA_priv_decrypt_key.decrypt(encrypted_fernet_key, 
            padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
            )
        )

    # return encrypted message, public encrypt key must be set BEFORE this
    def main_encrypt(self, message_obj) -> Message:
        encrypted = Message(message_obj.sender, message_obj.recipient, message_obj.message, message_obj.fernet_key)
        encrypted.fernet_key = binascii.hexlify(self.gen_fernet_encrypt_key()).decode()
        encrypted.message = self.fernet_encrypt_message(message_obj.message)
        return encrypted

    #decrypt message, private key must be set BEFORE this
    def main_decrypt(self, message_obj) -> Message:
        decrypted = Message(message_obj.sender, message_obj.recipient, message_obj.message, message_obj.fernet_key)
        decrypted.fernet_key = self.decrypt_fernet_key(binascii.unhexlify(message_obj.fernet_key.encode())).decode()
        decrypted.message = self.fernet_decrypt_message(message_obj.message, decrypted.fernet_key.encode())
        return decrypted

    def hash_string(self, password : str) ->str :
        digest = hashes.Hash(hashes.SHA256(), default_backend())
        digest.update(password.encode())
        b = digest.finalize()
        return binascii.hexlify(b).decode()         




    
    