# p2p_app/discovery.py
import socket
import logging # Add logging
import struct
import threading
import time
import json
from . import config
from .peer import Peer

discovered_peers = {} # Dictionary to store discovered peers { (ip, port): Peer_object }
my_username = "DefaultUser" # Will be updated by user input
my_server_port = config.SERVER_PORT # Port our P2P server runs on
my_ip = None # Will store our actual IP address

# Configure logging if not already done globally in the module
# logging.basicConfig(level=logging.INFO)

def get_local_ip():
    # ... (previous code for reference, to be replaced)
    # try:
    #     s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    #     s.connect(("8.8.8.8", 80))
    #     ip = s.getsockname()[0]
    #     s.close()
    #     return ip
    # except Exception:
    #     return "127.0.0.1"
    # ...

    candidate_ips = []
    try:
        hostname = socket.gethostname()
        # This can return multiple IPs, including loopback, LAN, WAN
        all_ips_info = socket.getaddrinfo(hostname, None)
        for info in all_ips_info:
            if info[0] == socket.AF_INET: # Check for IPv4
                ip = info[4][0]
                if ip not in candidate_ips:
                    candidate_ips.append(ip)
    except socket.gaierror:
        logging.warning("Could not get IP addresses via getaddrinfo(hostname). Trying gethostbyname_ex.")
        try:
            hostname = socket.gethostname()
            # gethostbyname_ex can return a list of IPs for the host
            # The last element of the tuple is a list of IP addresses
            name, aliases, ipaddrs = socket.gethostbyname_ex(hostname)
            for ip in ipaddrs:
                if ip not in candidate_ips:
                    candidate_ips.append(ip)
        except socket.gaierror:
            logging.warning("Could not determine IP address using gethostbyname_ex. Will try a direct socket connection method.")
            pass # Fall through to next method

    # If previous methods failed or yielded empty lists, try the connect method as a fallback for a single IP
    if not candidate_ips:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.1) # Avoid long hangs
            s.connect(("8.8.8.8", 80)) # Connect to a public IP
            ip = s.getsockname()[0]
            if ip and ip not in candidate_ips:
                candidate_ips.append(ip)
            s.close()
        except Exception as e:
            logging.warning(f"Could not determine IP via connect method: {e}")

    logging.info(f"Candidate IPs for local machine: {candidate_ips}")

    # Prioritize private IPs
    private_ip_ranges = [
        ("10.0.0.0", "10.255.255.255"),
        ("172.16.0.0", "172.31.255.255"),
        ("192.168.0.0", "192.168.255.255")
    ]

    def ip_to_int(ip_str):
        parts = list(map(int, ip_str.split('.')))
        return (parts[0] << 24) + (parts[1] << 16) + (parts[2] << 8) + parts[3]

    for ip in candidate_ips:
        if ip == "127.0.0.1":
            continue
        try:
            ip_int = ip_to_int(ip)
            for r_start, r_end in private_ip_ranges:
                if ip_to_int(r_start) <= ip_int <= ip_to_int(r_end):
                    logging.info(f"Selected private LAN IP: {ip}")
                    return ip
        except ValueError: # If IP is not in expected format
            continue


    # If no private IP, take the first non-loopback
    for ip in candidate_ips:
        if ip != "127.0.0.1":
            logging.info(f"No private LAN IP found. Selected first non-loopback IP: {ip}")
            return ip

    logging.warning("No suitable non-loopback IP found. Falling back to 127.0.0.1.")
    return "127.0.0.1"

def set_identity(username, server_port):
    global my_username, my_server_port, my_ip
    my_username = username
    my_server_port = server_port
    my_ip = get_local_ip()

def send_discovery_message(sock):
    message = {
        "username": my_username,
        "port": my_server_port,
        "type": "discovery",
        "ip": my_ip  # Include our actual IP
    }
    message_bytes = json.dumps(message).encode('utf-8')
    try:
        # Send to the standard multicast port that all instances listen on
        sock.sendto(message_bytes, (config.MULTICAST_ADDRESS, config.MULTICAST_PORT))
        logging.info(f"Sent discovery message: {message}")
    except Exception as e:
        logging.error(f"Error sending discovery message: {e}", exc_info=True)

def listen_for_discovery_messages(sock):
    while True:
        try:
            data, addr = sock.recvfrom(config.BUFFER_SIZE)
            message_str = data.decode('utf-8')
            message = json.loads(message_str)
            logging.info(f"Received message: {message} from {addr}")

            if message.get("type") == "discovery":
                # Use the IP from the message if available, otherwise from addr
                peer_ip = message.get("ip", addr[0])
                peer_port = message.get("port")
                peer_username = message.get("username")

                if not peer_ip or not peer_port or not peer_username:
                    logging.warning(f"Incomplete discovery message from {addr}: {message}")
                    continue

                # Avoid discovering self by checking both IP and port
                if (peer_ip == my_ip or peer_ip == "127.0.0.1") and peer_port == my_server_port and peer_username == my_username:
                    logging.info(f"Ignoring self-discovery message from {peer_ip}:{peer_port}")
                    continue

                peer_key = (peer_ip, peer_port)
                if peer_key not in discovered_peers or discovered_peers[peer_key].username != peer_username:
                    logging.info(f"Discovered new peer: {peer_username} at {peer_ip}:{peer_port}")

                discovered_peers[peer_key] = Peer(peer_ip, peer_port, peer_username)

        except json.JSONDecodeError:
            logging.error(f"Error decoding JSON from {addr}: {data.decode('utf-8', errors='ignore')}", exc_info=True)
        except socket.timeout:
            continue # Expected if no messages
        except Exception as e:
            logging.error(f"Error listening for discovery messages: {e}", exc_info=True)
            time.sleep(1) # Avoid rapid spamming of errors

def start_discovery(username="P2PUser", server_port_to_advertise=config.SERVER_PORT):
    set_identity(username, server_port_to_advertise)

    # Create UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # Bind to the standard multicast port
    sock.bind(('', config.MULTICAST_PORT))

    # Tell the operating system to add the socket to the multicast group
    # on all interfaces.
    group = socket.inet_aton(config.MULTICAST_ADDRESS)
    mreq = struct.pack('4sL', group, socket.INADDR_ANY)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    sock.settimeout(1.0) # Timeout for recvfrom

    # NEW: Set the outgoing interface for multicast messages
    if my_ip and my_ip != "127.0.0.1":
        try:
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(my_ip))
            logging.info(f"Multicast sending interface set to: {my_ip}")
        except socket.error as e:
            logging.warning(f"Failed to set multicast sending interface IP_MULTICAST_IF to {my_ip}: {e}. Using system default.")
    else:
        logging.info("Multicast sending interface not explicitly set (my_ip is 127.0.0.1 or None). Using system default.")

    logging.info(f"Starting P2P discovery. My Info: {my_username} on port {my_server_port}. Listening on {config.MULTICAST_ADDRESS}:{config.MULTICAST_PORT}")
    logging.info(f"My IP address: {my_ip}")

    # Start listener thread
    listener_thread = threading.Thread(target=listen_for_discovery_messages, args=(sock,), daemon=True)
    listener_thread.start()

    # Periodically send discovery messages
    def broadcast_loop():
        while True:
            send_discovery_message(sock)
            time.sleep(config.BROADCAST_INTERVAL)

    broadcast_thread = threading.Thread(target=broadcast_loop, args=(), daemon=True)
    broadcast_thread.start()

    # Periodically clean up old peers
    def cleanup_loop():
        while True:
            current_time = time.time()
            peers_to_remove = [
                key for key, peer_obj in discovered_peers.items()
                if current_time - peer_obj.last_seen > config.PEER_TIMEOUT
            ]
            for key in peers_to_remove:
                logging.info(f"Peer timed out: {discovered_peers[key].username}")
                del discovered_peers[key]
            time.sleep(config.PEER_TIMEOUT / 2) # Check more frequently than timeout

    cleanup_thread = threading.Thread(target=cleanup_loop, args=(), daemon=True)
    cleanup_thread.start()

    logging.info("Discovery sender, listener, and cleanup threads started.")
    # Note: This function will return, threads run in background.
    # In a real app, you'd have a way to stop these threads gracefully.

def get_discovered_peers():
    # Return a list of peer dicts for API use
    return [peer.to_dict() for peer in discovered_peers.values()]

# Example usage (for testing this module directly)
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
    start_discovery("TestUser_Discovery", 50001)
    try:
        while True:
            logging.info(f"Currently known peers: {get_discovered_peers()}")
            time.sleep(5)
    except KeyboardInterrupt:
        logging.info("Stopping discovery test.")
