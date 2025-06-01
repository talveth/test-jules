# p2p_app/config.py
import socket

MULTICAST_ADDRESS = "239.255.255.250"  # Example multicast address
MULTICAST_PORT = 19000  # Port for multicast discovery
SERVER_PORT = 19001  # Default port for the P2P server
BUFFER_SIZE = 1024
BROADCAST_INTERVAL = 5  # seconds
PEER_TIMEOUT = 30  # seconds

def find_available_port(start_port=SERVER_PORT, max_attempts=100):
    """Find an available port starting from start_port."""
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', port))
                return port
        except OSError:
            continue
    raise RuntimeError(f"Could not find an available port after {max_attempts} attempts")
