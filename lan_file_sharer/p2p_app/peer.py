# p2p_app/peer.py
import time

class Peer:
    def __init__(self, address, port, username):
        self.address = address
        self.port = port
        self.username = username
        self.last_seen = time.time()

    def __repr__(self):
        return f"Peer({self.address}:{self.port}, {self.username})"

    def to_dict(self):
        return {
            "address": self.address,
            "port": self.port,
            "username": self.username,
            "last_seen": self.last_seen
        }

    @staticmethod
    def from_dict(data):
        peer = Peer(data["address"], data["port"], data["username"])
        peer.last_seen = data.get("last_seen", time.time())
        return peer
