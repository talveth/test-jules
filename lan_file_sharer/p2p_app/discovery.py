# p2p_app/discovery.py
import socket
import struct
import threading
import time
import json
from . import config
from .peer import Peer

discovered_peers = {} # Dictionary to store discovered peers { (ip, port): Peer_object }
my_username = "DefaultUser" # Will be updated by user input
my_server_port = config.SERVER_PORT # Port our P2P server runs on

def set_identity(username, server_port):
    global my_username, my_server_port
    my_username = username
    my_server_port = server_port

def send_discovery_message(sock):
    message = {
        "username": my_username,
        "port": my_server_port,
        "type": "discovery"
    }
    message_bytes = json.dumps(message).encode('utf-8')
    try:
        sock.sendto(message_bytes, (config.MULTICAST_ADDRESS, config.MULTICAST_PORT))
        # print(f"Sent discovery: {message}")
    except Exception as e:
        print(f"Error sending discovery message: {e}")

def listen_for_discovery_messages(sock):
    while True:
        try:
            data, addr = sock.recvfrom(config.BUFFER_SIZE)
            message_str = data.decode('utf-8')
            message = json.loads(message_str)
            # print(f"Received message: {message} from {addr}")

            if message.get("type") == "discovery":
                peer_ip = addr[0]
                peer_port = message.get("port")
                peer_username = message.get("username")

                if not peer_ip or not peer_port or not peer_username:
                    print(f"Incomplete discovery message from {addr}: {message}")
                    continue

                # Avoid discovering self if message somehow looped back
                # This check might need refinement based on how local IP is determined
                # For now, if it's our multicast port and username, ignore,
                # but ideally check against own actual IP.
                # if peer_ip == "127.0.0.1" and peer_port == my_server_port and peer_username == my_username:
                #    continue


                peer_key = (peer_ip, peer_port)
                if peer_key not in discovered_peers or discovered_peers[peer_key].username != peer_username:
                    print(f"Discovered new peer: {peer_username} at {peer_ip}:{peer_port}")

                discovered_peers[peer_key] = Peer(peer_ip, peer_port, peer_username)

        except json.JSONDecodeError:
            print(f"Error decoding JSON from {addr}: {data.decode('utf-8', errors='ignore')}")
        except socket.timeout:
            continue # Expected if no messages
        except Exception as e:
            print(f"Error listening for discovery messages: {e}")
            time.sleep(1) # Avoid rapid spamming of errors

def start_discovery(username="P2PUser", server_port_to_advertise=config.SERVER_PORT):
    set_identity(username, server_port_to_advertise)

    # Create UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # Bind to the server address for listening
    # Listen on all interfaces for multicast messages
    sock.bind(('', config.MULTICAST_PORT))

    # Tell the operating system to add the socket to the multicast group
    # on all interfaces.
    group = socket.inet_aton(config.MULTICAST_ADDRESS)
    mreq = struct.pack('4sL', group, socket.INADDR_ANY)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    sock.settimeout(1.0) # Timeout for recvfrom

    print(f"Starting P2P discovery. My Info: {my_username} on port {my_server_port}. Listening on {config.MULTICAST_ADDRESS}:{config.MULTICAST_PORT}")

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
                print(f"Peer timed out: {discovered_peers[key].username}")
                del discovered_peers[key]
            time.sleep(config.PEER_TIMEOUT / 2) # Check more frequently than timeout

    cleanup_thread = threading.Thread(target=cleanup_loop, args=(), daemon=True)
    cleanup_thread.start()

    print("Discovery sender, listener, and cleanup threads started.")
    # Note: This function will return, threads run in background.
    # In a real app, you'd have a way to stop these threads gracefully.

def get_discovered_peers():
    # Return a list of peer dicts for API use
    return [peer.to_dict() for peer in discovered_peers.values()]

# Example usage (for testing this module directly)
if __name__ == "__main__":
    start_discovery("TestUser_Discovery", 50001)
    try:
        while True:
            print(f"Currently known peers: {get_discovered_peers()}")
            time.sleep(5)
    except KeyboardInterrupt:
        print("Stopping discovery test.")
