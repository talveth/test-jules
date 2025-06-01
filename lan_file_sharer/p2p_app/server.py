# p2p_app/server.py
from flask import Flask, jsonify, request, send_file, Response, stream_with_context, send_from_directory
import requests # For making requests to other peers
import urllib.parse # For decoding URL parameters
from . import discovery
from . import file_handler
from . import config
import os # For __main__ test content
import uuid
from werkzeug.utils import secure_filename

# Get the absolute path to the frontend directory
FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'frontend'))
# Create a directory for uploaded files
UPLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'uploads'))
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__, 
    static_folder=os.path.join(FRONTEND_DIR, 'js'),
    static_url_path='/js')

# Serve CSS files
@app.route('/css/<path:filename>')
def serve_css(filename):
    return send_from_directory(os.path.join(FRONTEND_DIR, 'css'), filename)

# Serve the main frontend page
@app.route('/')
def index():
    return send_from_directory(os.path.join(FRONTEND_DIR, 'html'), 'index.html')

# --- P2P Endpoints (called by other peers) ---
@app.route('/p2p/hello', methods=['GET'])
def p2p_hello():
    return jsonify({
        "message": f"Hello from {discovery.my_username}!",
        "username": discovery.my_username,
        "server_port": discovery.my_server_port
    })

@app.route('/p2p/list_files', methods=['GET'])
def p2p_list_files():
    shared_files = file_handler.get_shared_files_metadata_for_remote()
    return jsonify(shared_files)

@app.route('/p2p/download_file/<file_id>', methods=['POST'])
def p2p_download_file(file_id):
    data = request.get_json()
    password_attempt = data.get("password", "") if data else ""
    filepath, password_hash = file_handler.get_file_path_and_password_hash(file_id)
    if not filepath:
        return jsonify({"error": "File not found or not shared"}), 404
    if not os.path.exists(filepath): # Double check file still exists
        file_handler.remove_shared_file(file_id) # Clean up metadata if file is gone
        return jsonify({"error": "File no longer available on server"}), 410 # Gone
    if password_hash:
        if not file_handler.verify_password(file_id, password_attempt):
            return jsonify({"error": "Incorrect password"}), 403
    try:
        return send_file(filepath, as_attachment=True)
    except Exception as e:
        print(f"Error sending file {filepath}: {e}")
        return jsonify({"error": "Could not send file"}), 500

# --- API Endpoints for the local Frontend (existing ones) ---
@app.route('/api/identity', methods=['GET', 'POST'])
def api_identity():
    if request.method == 'POST':
        data = request.json
        username = data.get('username')
        if not username:
            return jsonify({"error": "Username is required"}), 400
        discovery.set_identity(username, discovery.my_server_port)
        return jsonify({"message": "Username updated", "username": username})
    else: # GET
        return jsonify({
            "username": discovery.my_username,
            "server_port": discovery.my_server_port,
        })

@app.route('/api/peers', methods=['GET'])
def api_get_peers():
    peers = discovery.get_discovered_peers()
    return jsonify(peers)

@app.route('/api/shared_files', methods=['GET', 'POST'])
def api_manage_shared_files():
    if request.method == 'POST':
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400

        # Get password from form data
        password = request.form.get('password', '')
        
        # Secure the filename and create a unique path
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4()}_{filename}"
        filepath = os.path.join(UPLOAD_DIR, unique_filename)
        
        # Save the file
        file.save(filepath)
        
        # Add to shared files
        file_id, message = file_handler.add_shared_file(filepath, password)
        if file_id:
            return jsonify({
                "message": message,
                "file_id": file_id,
                "name": filename
            }), 200
        else:
            # Clean up the file if sharing failed
            if os.path.exists(filepath):
                os.remove(filepath)
            return jsonify({"error": message}), 400
    else: # GET
        return jsonify(file_handler.get_shared_files_metadata_for_remote())

@app.route('/api/shared_files/<file_id>', methods=['DELETE'])
def api_remove_shared_file(file_id):
    if file_handler.remove_shared_file(file_id):
        return jsonify({"message": "File unshared successfully"}), 200
    else:
        return jsonify({"error": "File not found or could not be unshared"}), 404

# --- NEW API Endpoints for Frontend to interact with OTHER PEERS (Proxy Endpoints) ---

@app.route('/api/peers/<string:peer_address_encoded>/<int:peer_port>/files', methods=['GET'])
def api_get_peer_files(peer_address_encoded, peer_port):
    peer_address = urllib.parse.unquote(peer_address_encoded)
    target_url = f"http://{peer_address}:{peer_port}/p2p/list_files"
    print(f"Proxying request for file list from {discovery.my_username} to {target_url}")
    try:
        response = requests.get(target_url, timeout=5) # 5 second timeout
        response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
        return jsonify(response.json())
    except requests.exceptions.Timeout:
        return jsonify({"error": f"Peer {peer_address}:{peer_port} timed out."}), 504 # Gateway Timeout
    except requests.exceptions.RequestException as e:
        print(f"Error fetching files from peer {peer_address}:{peer_port} - {e}")
        # Try to return peer's error if available and it's JSON
        try:
            if e.response is not None and 'application/json' in e.response.headers.get('Content-Type',''):
                return jsonify(e.response.json()), e.response.status_code
        except: # Fallback if error response is not JSON
            pass
        return jsonify({"error": f"Could not connect to peer {peer_address}:{peer_port} or peer returned an error."}), 502 # Bad Gateway
    except Exception as e:
        print(f"Generic error fetching files from peer {peer_address}:{peer_port} - {e}")
        return jsonify({"error": "An unexpected error occurred while fetching peer files."}), 500


@app.route('/api/peers/<string:peer_address_encoded>/<int:peer_port>/download/<file_id>', methods=['POST'])
def api_download_from_peer(peer_address_encoded, peer_port, file_id):
    peer_address = urllib.parse.unquote(peer_address_encoded)
    password_data = request.get_json()
    password = password_data.get("password", "") if password_data else ""

    target_url = f"http://{peer_address}:{peer_port}/p2p/download_file/{file_id}"
    print(f"Proxying download request for file {file_id} from {peer_address}:{peer_port}")

    try:
        p2p_response = requests.post(target_url, json={"password": password}, stream=True, timeout=(5, 300)) # 5s connect, 300s read timeout
        p2p_response.raise_for_status() # Important to check for 4xx/5xx errors from peer

        # If the peer returns a JSON error (e.g., wrong password), relay it
        if 'application/json' in p2p_response.headers.get('Content-Type', '').lower():
            error_json = p2p_response.json() # This consumes the content, so do it carefully
            print(f"Peer {peer_address}:{peer_port} returned JSON error for download: {error_json}")
            return jsonify({"error": error_json.get("error", "Peer error during download")}), p2p_response.status_code

        # Stream the response back to the client
        def generate_chunks():
            for chunk in p2p_response.iter_content(chunk_size=8192): # 8KB chunks
                yield chunk

        headers = {}
        if 'Content-Disposition' in p2p_response.headers:
            headers['Content-Disposition'] = p2p_response.headers['Content-Disposition']
        # Ensure correct Content-Type if not an error (it shouldn't be JSON here)
        if 'Content-Type' in p2p_response.headers and 'application/json' not in p2p_response.headers['Content-Type'].lower():
             headers['Content-Type'] = p2p_response.headers['Content-Type']
        else: # Fallback if peer doesn't set it correctly for file streams
            headers['Content-Type'] = 'application/octet-stream'


        return Response(stream_with_context(generate_chunks()), status=p2p_response.status_code, headers=headers)

    except requests.exceptions.Timeout:
        return jsonify({"error": f"Peer {peer_address}:{peer_port} timed out during download."}), 504
    except requests.exceptions.HTTPError as e:
        # This catches 4xx/5xx from the other peer that were not JSON
        # (e.g. if peer's Flask crashes, or returns non-JSON error page)
        print(f"HTTPError from peer {peer_address}:{peer_port} during download: {e.response.status_code} - {e.response.text[:200]}")
        try:
            error_content = e.response.json() # Try to parse if it is JSON despite headers
            return jsonify({"error": error_content.get("error", f"Peer error: {e.response.status_code}")}), e.response.status_code
        except:
            return jsonify({"error": f"Peer {peer_address}:{peer_port} returned error: {e.response.status_code}"}), e.response.status_code
    except requests.exceptions.RequestException as e:
        print(f"Error downloading from peer {peer_address}:{peer_port} - {e}")
        return jsonify({"error": f"Could not connect to peer {peer_address}:{peer_port} for download."}), 502
    except Exception as e:
        print(f"Generic error proxying download from peer {peer_address}:{peer_port} - {e}")
        return jsonify({"error": "An unexpected error occurred while proxying download."}), 500


# --- Server Runner ---
def run_server(port, debug=False):
    print(f"Starting P2P HTTP server on 0.0.0.0 port {port}")
    # Ensure discovery module knows the actual port being used by the server.
    # This is crucial if the port is dynamically assigned or changed from config.
    discovery.my_server_port = port
    # Using threaded=True allows Flask to handle multiple requests concurrently,
    # which is important for a responsive UI and for handling P2P requests
    # without blocking discovery threads or other API calls.
    app.run(host='0.0.0.0', port=port, debug=debug, threaded=True)

if __name__ == '__main__':
    # Mock discovery for standalone server testing
    class MockDiscovery:
        my_username = "ServerTestUser"
        my_server_port = config.SERVER_PORT # Use port from config
        def get_discovered_peers(self): return []
        def set_identity(self, uname, sport):
            self.my_username = uname
            self.my_server_port = sport # Update mock's port

    mock_discovery_instance = MockDiscovery()
    discovery.my_username = mock_discovery_instance.my_username
    discovery.my_server_port = mock_discovery_instance.my_server_port
    discovery.get_discovered_peers = mock_discovery_instance.get_discovered_peers
    discovery.set_identity = mock_discovery_instance.set_identity

    # Setup a test shared file for when server.py is run directly
    # This uses the actual file_handler module.
    test_shared_dir = "test_server_share_dir"
    test_file_name = "server_main_test.txt"
    test_file_path = os.path.join(test_shared_dir, test_file_name)

    os.makedirs(test_shared_dir, exist_ok=True)
    with open(test_file_path, "w") as f:
        f.write("This is a test file for server.py direct execution.")
    file_id, _ = file_handler.add_shared_file(test_file_path, password="test")

    print(f"Mocked discovery: User '{discovery.my_username}', Port {discovery.my_server_port}")
    print(f"Test shared file added: '{test_file_name}' (ID: {file_id})")
    print(f"Shared files list: {file_handler.get_shared_files_metadata_for_remote()}")

    # Run the server with the port from config
    run_server(port=config.SERVER_PORT, debug=True) # debug=True for easier testing

    # Cleanup after server stops (e.g., on Ctrl+C)
    print("Cleaning up test files...")
    if file_id:
        file_handler.remove_shared_file(file_id)
    if os.path.exists(test_file_path):
        os.remove(test_file_path)
    if os.path.exists(test_shared_dir) and not os.listdir(test_shared_dir):
        os.rmdir(test_shared_dir)
    print("Cleanup complete.")
