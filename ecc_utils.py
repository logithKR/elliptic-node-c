from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization, hashes

private_key = ec.generate_private_key(ec.SECP256R1())
public_key = private_key.public_key()

def encrypt_data(data: str):
    signature = private_key.sign(data.encode(), ec.ECDSA(hashes.SHA256()))
    return signature.hex()

def get_keys():
    return (
        private_key.private_numbers().private_value,
        public_key.public_numbers()
    )
