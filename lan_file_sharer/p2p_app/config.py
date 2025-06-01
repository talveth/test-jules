# p2p_app/config.py
MULTICAST_ADDRESS = "239.255.255.250"  # Example multicast address
MULTICAST_PORT = 19000  # Example port for discovery
SERVER_PORT = 19001 # Port for the P2P HTTP server, will be dynamic later if needed
BROADCAST_INTERVAL = 5  # Seconds between discovery broadcasts
PEER_TIMEOUT = 15  # Seconds before considering a peer offline
BUFFER_SIZE = 1024 # Buffer size for network operations
