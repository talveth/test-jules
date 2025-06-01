# p2p_app/file_handler.py
import os
import hashlib
import json

# This will store metadata about shared files
# Key: file_id (e.g., a hash of the path or a UUID)
# Value: dict {name, path, size, password_hash (optional), id}
shared_files_metadata = {}

def generate_file_id(filepath):
    # Simple ID generator based on path hash for now
    return hashlib.md5(filepath.encode()).hexdigest()

def add_shared_file(filepath, password=None):
    if not os.path.exists(filepath):
        print(f"Error: File not found - {filepath}")
        return None, "File not found"
    if not os.path.isfile(filepath):
        # For now, only single files. Folder sharing will be an enhancement.
        print(f"Error: Path is not a file - {filepath}")
        return None, "Path is not a file"

    file_id = generate_file_id(filepath)
    filename = os.path.basename(filepath)
    filesize = os.path.getsize(filepath)

    password_hash = None
    if password:
        # In a real app, use a strong hashing algorithm like bcrypt or scrypt
        password_hash = hashlib.sha256(password.encode()).hexdigest()

    shared_files_metadata[file_id] = {
        "id": file_id,
        "name": filename,
        "path": filepath, # Store full path for local access
        "size": filesize,
        "password_hash": password_hash
    }
    print(f"Sharing file: {filename} (ID: {file_id})")
    return file_id, "File added successfully"

def remove_shared_file(file_id):
    if file_id in shared_files_metadata:
        print(f"Stopped sharing file: {shared_files_metadata[file_id]['name']}")
        del shared_files_metadata[file_id]
        return True
    return False

def get_shared_files_metadata_for_remote():
    # Return a list of metadata suitable for sending to remote peers
    # (omitting local full path for security/privacy)
    files_for_remote = []
    for file_id, meta in shared_files_metadata.items():
        files_for_remote.append({
            "id": meta["id"],
            "name": meta["name"],
            "size": meta["size"],
            "has_password": bool(meta["password_hash"]) # Don't send the hash itself
        })
    return files_for_remote

def get_file_path_and_password_hash(file_id):
    meta = shared_files_metadata.get(file_id)
    if meta:
        return meta["path"], meta["password_hash"]
    return None, None

def verify_password(file_id, password_attempt):
    meta = shared_files_metadata.get(file_id)
    if not meta:
        return False # File not found
    if not meta["password_hash"]:
        return True # No password set for this file

    attempted_hash = hashlib.sha256(password_attempt.encode()).hexdigest()
    return attempted_hash == meta["password_hash"]

# Example usage (for testing this module directly)
if __name__ == '__main__':
    # Create dummy files for testing
    os.makedirs("test_share_dir", exist_ok=True)
    with open("test_share_dir/testfile1.txt", "w") as f:
        f.write("This is test file 1.")
    with open("test_share_dir/testfile2.txt", "w") as f:
        f.write("This is test file 2, with more content.")

    file_id1, _ = add_shared_file("test_share_dir/testfile1.txt")
    file_id2, _ = add_shared_file("test_share_dir/testfile2.txt", password="secure")

    print("\nShared files (for remote):")
    print(json.dumps(get_shared_files_metadata_for_remote(), indent=2))

    print(f"\nPath for {file_id1}: {get_file_path_and_password_hash(file_id1)[0]}")

    print(f"\nVerifying password for {file_id2} (correct): {verify_password(file_id2, 'secure')}")
    print(f"Verifying password for {file_id2} (incorrect): {verify_password(file_id2, 'wrong')}")
    print(f"Verifying password for {file_id1} (no password): {verify_password(file_id1, '')}")

    remove_shared_file(file_id1)
    print("\nShared files after removing one:")
    print(json.dumps(get_shared_files_metadata_for_remote(), indent=2))

    # Cleanup dummy files
    os.remove("test_share_dir/testfile1.txt")
    os.remove("test_share_dir/testfile2.txt")
    os.rmdir("test_share_dir")
