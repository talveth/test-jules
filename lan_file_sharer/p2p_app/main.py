# p2p_app/main.py
import time
import threading # For running server in a separate thread
import os # For example shared file
from . import discovery
from . import server
from . import config
from . import file_handler # For potential initial setup or testing

def main():
    print("Starting P2P File Sharing Application...")

    my_username = input("Enter your username: ")
    
    # Find an available port for this instance
    try:
        p2p_server_port = config.find_available_port()
        print(f"Using port {p2p_server_port} for this instance")
    except RuntimeError as e:
        print(f"Error: {e}")
        return

    # Set identity in discovery module first, so broadcasts are correct from the start
    # This also sets discovery.my_server_port which server.py will use via discovery module
    discovery.set_identity(username=my_username, server_port=p2p_server_port)

    # Start discovery services (threads for listening and broadcasting)
    # discovery.start_discovery will use the username and port set by set_identity
    discovery.start_discovery(username=my_username, server_port_to_advertise=p2p_server_port)

    # Example: Share a dummy file at startup for testing
    # You'd normally do this via the frontend API
    # Ensure "local_shares" directory exists
    # os.makedirs("local_shares", exist_ok=True)
    # dummy_file_path = "local_shares/auto_shared.txt"
    # with open(dummy_file_path, "w") as f:
    #     f.write(f"This file was automatically shared by {my_username} at {time.ctime()}")
    # file_handler.add_shared_file(dummy_file_path, password="test")
    # print(f"Added example shared file: {dummy_file_path}")


    print(f"P2P Server will run on port {p2p_server_port}.")
    print(f"Discovery active for user '{my_username}' advertising port {p2p_server_port}.")
    print(f"To access the web UI (once developed), open a browser to http://127.0.0.1:{p2p_server_port} or your LAN IP.")

    # Run the Flask server.
    # server.run_server now uses app.run(..., threaded=True),
    # which means Flask handles requests in separate threads.
    # The call to server.run_server() itself will block the main thread here,
    # which is fine as discovery threads are daemons and will exit when main does.
    server.run_server(port=p2p_server_port, debug=False) # debug=False is better for this stage

    # This line will be reached when server stops (e.g. Ctrl+C)
    print("Application shutting down.")

    # Clean up example shared file if it was created
    # if os.path.exists(dummy_file_path):
    #     file_handler.remove_shared_file(file_handler.generate_file_id(dummy_file_path))
    #     os.remove(dummy_file_path)
    # if os.path.exists("local_shares") and not os.listdir("local_shares"):
    #     os.rmdir("local_shares")

if __name__ == "__main__":
    main()
