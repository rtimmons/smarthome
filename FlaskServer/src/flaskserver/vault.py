from cryptography.fernet import Fernet
import yaml


class Vault:
    def __init__(self, key: str):
        self.fernet = Fernet(bytes(key, "utf-8"))
        with open("./secrets.yml") as handle:
            self.db = yaml.safe_load(handle)
        decr = self.decrypt("__vault__hello")
        assert decr == "hello"

    def encrypt(self, value: str):
        out = self.fernet.encrypt(bytes(value, "utf-8"))
        return str(out, "utf-8")

    def decrypt(self, secret_id):
        decrypted = str(self.fernet.decrypt(bytes(self.db[secret_id], 'utf-8')), 'utf-8')
        return decrypted
