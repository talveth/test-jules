// frontend/js/app.js
document.addEventListener('DOMContentLoaded', () => {
    // --- HTML Element References ---
    const usernameInput = document.getElementById('username-input');
    const setUsernameBtn = document.getElementById('set-username-btn');
    const currentUsernameDisplay = document.getElementById('current-username-display');

    const fileInput = document.getElementById('file-input');
    const dropZone = document.getElementById('drop-zone');
    const mySharedFilesList = document.getElementById('my-shared-files-list');

    const peerListUL = document.getElementById('peer-list'); // Changed from peerList
    const remoteFilesListUL = document.getElementById('remote-files-list'); // Changed from remoteFilesList
    const selectedPeerUsernameDisplay = document.getElementById('selected-peer-username');
    const passwordPromptDiv = document.getElementById('password-prompt'); // Changed from passwordPrompt
    const downloadPasswordInput = document.getElementById('download-password-input');
    const submitPasswordBtn = document.getElementById('submit-password-btn');

    let currentUsername = '';
    let currentSelectedPeer = null; // Stores {username, address, port} of the peer whose files are being viewed
    let fileToDownloadWithPassword = null; // Stores {peerAddress, peerPort, fileId, fileName}

    const API_BASE_URL = `http://${window.location.hostname}:19001/api`;

    // Interval timers
    let peerFetchInterval = null;
    let myFilesFetchInterval = null;

    // --- Initialization ---
    fetchIdentity();

    // --- Event Listeners ---
    setUsernameBtn.addEventListener('click', setUsernameAndGoOnline);
    dropZone.addEventListener('dragover', handleDragOver);
    dropZone.addEventListener('dragleave', handleDragLeave);
    dropZone.addEventListener('drop', handleDrop);
    fileInput.addEventListener('change', handleFileSelect);
    submitPasswordBtn.addEventListener('click', handlePasswordSubmitForDownload);

    // --- Core Functions ---
    async function fetchIdentity() {
        try {
            const response = await fetch(`${API_BASE_URL}/identity`);
            if (response.ok) {
                const data = await response.json();
                if (data.username && data.username !== "DefaultUser" && data.username !== "ServerTestUser" && data.username !== "DummyUser") {
                    updateCurrentUsername(data.username);
                    usernameInput.value = data.username; // Pre-fill if already set
                    usernameInput.disabled = true;
                    setUsernameBtn.disabled = true;
                    setUsernameBtn.textContent = 'Username Set';
                    console.log('Resuming with username:', currentUsername);
                    startPeriodicFetches();
                } else {
                    updateCurrentUsername('');
                }
            } else {
                 updateCurrentUsername(''); // Ensure UI reflects no active user
            }
        } catch (error) {
            console.warn('Could not fetch initial identity:', error);
            updateCurrentUsername('');
        }
    }

    async function setUsernameAndGoOnline() {
        const username = usernameInput.value.trim();
        if (!username) {
            alert('Please enter a username.');
            return;
        }
        try {
            const response = await fetch(`${API_BASE_URL}/identity`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username: username })
            });
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            updateCurrentUsername(data.username);
            usernameInput.disabled = true;
            setUsernameBtn.disabled = true;
            setUsernameBtn.textContent = 'Username Set';
            console.log('Username set to:', currentUsername);
            startPeriodicFetches();
        } catch (error) {
            console.error('Error setting username:', error);
            alert(`Failed to set username: ${error.message}`);
        }
    }

    function updateCurrentUsername(username) {
        currentUsername = username;
        currentUsernameDisplay.textContent = username || "Not Set";
    }

    function startPeriodicFetches() {
        if (!currentUsername) return;
        stopPeriodicFetches(); // Clear existing intervals if any

        fetchPeers();
        fetchMySharedFiles();

        peerFetchInterval = setInterval(fetchPeers, 5000); // Fetch peers every 5 seconds
        myFilesFetchInterval = setInterval(fetchMySharedFiles, 10000); // Fetch own shared files every 10 seconds
        console.log("Periodic fetching started.");
    }

    function stopPeriodicFetches() {
        if (peerFetchInterval) clearInterval(peerFetchInterval);
        if (myFilesFetchInterval) clearInterval(myFilesFetchInterval);
        peerFetchInterval = null;
        myFilesFetchInterval = null;
        console.log("Periodic fetching stopped.");
    }

    // --- Peer Discovery and Display ---
    async function fetchPeers() {
        if (!currentUsername) return;
        try {
            const response = await fetch(`${API_BASE_URL}/peers`);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const peers = await response.json();
            renderPeers(peers);
        } catch (error) {
            console.error('Error fetching peers:', error);
            // Optionally clear peer list or show error in UI
            // peerListUL.innerHTML = '<li>Error fetching peers.</li>';
        }
    }

    function renderPeers(peers) {
        peerListUL.innerHTML = ''; // Clear existing list
        if (peers.length === 0) {
            peerListUL.innerHTML = '<li>No other users online.</li>';
            return;
        }
        peers.forEach(peer => {
            // Do not list self
            if (peer.username === currentUsername && peer.address === window.location.hostname) { // Basic self-check
                 // A more robust self-check would involve comparing against the actual IP and port our backend uses
                 // This is tricky because frontend doesn't know backend's external IP easily
                 // For now, this username check is a simple heuristic
                return;
            }

            const li = document.createElement('li');
            li.textContent = `${peer.username} (${peer.address}:${peer.port})`;
            li.dataset.username = peer.username;
            li.dataset.address = peer.address;
            li.dataset.port = peer.port;
            li.addEventListener('click', () => handlePeerSelect(peer));
            peerListUL.appendChild(li);
        });
    }

    async function handlePeerSelect(peer) {
        console.log('Selected peer:', peer);
        currentSelectedPeer = peer;
        selectedPeerUsernameDisplay.textContent = peer.username;
        remoteFilesListUL.innerHTML = '<li>Loading files...</li>';
        passwordPromptDiv.style.display = 'none'; // Hide password prompt

        // Construct the API endpoint for fetching files from a specific peer via our backend proxy
        // The peer address might contain dots, so URL encoding is important.
        const encodedPeerAddress = encodeURIComponent(peer.address);
        const filesUrl = `${API_BASE_URL}/peers/${encodedPeerAddress}/${peer.port}/files`;

        try {
            const response = await fetch(filesUrl);
            if (!response.ok) {
                 const errorData = await response.json();
                throw new Error(errorData.error || `Failed to fetch files for ${peer.username}`);
            }
            const files = await response.json();
            renderRemoteFiles(files, peer);
        } catch (error) {
            console.error('Error fetching remote files:', error);
            remoteFilesListUL.innerHTML = `<li>Error fetching files: ${error.message}</li>`;
        }
    }

    function renderRemoteFiles(files, peer) {
        remoteFilesListUL.innerHTML = '';
        if (files.length === 0) {
            remoteFilesListUL.innerHTML = '<li>This user is not sharing any files.</li>';
            return;
        }
        files.forEach(file => {
            const li = document.createElement('li');
            li.textContent = `${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB)`;

            const downloadBtn = document.createElement('button');
            downloadBtn.textContent = 'Download';
            downloadBtn.onclick = () => prepareDownload(peer, file);

            li.appendChild(downloadBtn);
            remoteFilesListUL.appendChild(li);
        });
    }

    // --- Own Shared Files Display ---
    async function fetchMySharedFiles() {
        if (!currentUsername) return;
        try {
            const response = await fetch(`${API_BASE_URL}/shared_files`);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const files = await response.json();
            renderMySharedFiles(files);
        } catch (error) {
            console.error('Error fetching my shared files:', error);
        }
    }

    function renderMySharedFiles(files) {
        mySharedFilesList.innerHTML = '';
        if (files.length === 0) {
            mySharedFilesList.innerHTML = '<li>You are not sharing any files.</li>';
            return;
        }
        files.forEach(file => {
            const li = document.createElement('li');
            li.textContent = `${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB) ${file.has_password ? '(Protected)' : ''}`;

            const unshareBtn = document.createElement('button');
            unshareBtn.textContent = 'Unshare';
            unshareBtn.style.backgroundColor = '#d9534f'; // Reddish color for delete
            unshareBtn.onclick = () => unshareFile(file.id);

            li.appendChild(unshareBtn);
            mySharedFilesList.appendChild(li);
        });
    }

    async function unshareFile(fileId) {
        if (!confirm("Are you sure you want to stop sharing this file?")) return;
        try {
            const response = await fetch(`${API_BASE_URL}/shared_files/${fileId}`, { method: 'DELETE' });
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || `HTTP error! ${response.status}`);
            }
            console.log(`File ${fileId} unshared.`);
            fetchMySharedFiles(); // Refresh list
        } catch (error) {
            console.error('Error unsharing file:', error);
            alert(`Failed to unshare file: ${error.message}`);
        }
    }

    // --- File Sharing (Drag/Drop, Input) ---
    function handleDragOver(event) {
        event.preventDefault();
        dropZone.classList.add('dragover');
    }

    function handleDragLeave() {
        dropZone.classList.remove('dragover');
    }

    function handleDrop(event) {
        event.preventDefault();
        dropZone.classList.remove('dragover');
        if (event.dataTransfer.files.length > 0) {
            handleFilesForSharing(event.dataTransfer.files);
        }
    }

    function handleFileSelect(event) {
        if (event.target.files.length > 0) {
            handleFilesForSharing(event.target.files);
        }
    }

    async function handleFilesForSharing(files) {
        if (!currentUsername) {
            alert("Please set your username before sharing files.");
            return;
        }
        console.log('Files selected for sharing:', files);

        for (const file of files) {
            const simulatedPath = prompt(`Enter the FULL ABSOLUTE PATH for '${file.name}' on the server machine (this is a temporary measure):`);
            if (!simulatedPath) {
                alert(`Sharing cancelled for ${file.name}. Path is required.`);
                continue;
            }
            const password = prompt(`Enter an optional password for ${file.name} (leave blank for none):`) || "";

            try {
                const response = await fetch(`${API_BASE_URL}/shared_files`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ filepath: simulatedPath, password: password })
                });
                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
                }
                const data = await response.json();
                console.log(`File ${simulatedPath} shared:`, data);
                fetchMySharedFiles(); // Refresh list
                alert(`File '${file.name}' (path: ${simulatedPath}) is now shared. ID: ${data.file_id}.`);
            } catch (error) {
                console.error('Error sharing file:', error);
                alert(`Failed to share file ${file.name}: ${error.message}`);
            }
        }
        fileInput.value = ''; // Reset file input
    }

    // --- File Downloading ---
    function prepareDownload(peer, file) {
        fileToDownloadWithPassword = {
            peerAddress: peer.address,
            peerPort: peer.port,
            fileId: file.id,
            fileName: file.name
        };

        if (file.has_password) {
            passwordPromptDiv.style.display = 'block';
            downloadPasswordInput.value = ''; // Clear previous password
            downloadPasswordInput.focus();
        } else {
            passwordPromptDiv.style.display = 'none';
            initiateDownload(""); // No password needed
        }
    }

    async function handlePasswordSubmitForDownload() {
        const password = downloadPasswordInput.value;
        if (!password && fileToDownloadWithPassword && (await checkFileNeedsPassword(fileToDownloadWithPassword))) {
            // This check is a bit redundant if file.has_password was true, but double check
            alert("Password is required for this file.");
            return;
        }
        initiateDownload(password);
    }

    // Helper to re-check if password is required, in case the file.has_password flag was stale
    // This is more of a conceptual check; the primary flag is from the file listing.
    async function checkFileNeedsPassword(fileDetails) {
        // This is tricky without re-fetching file list. For now, rely on initial `file.has_password`.
        // In a more robust system, the download attempt itself would confirm if password was needed and failed.
        const peerFilesUrl = `${API_BASE_URL}/peers/${encodeURIComponent(fileDetails.peerAddress)}/${fileDetails.peerPort}/files`;
        try {
            const response = await fetch(peerFilesUrl);
            const files = await response.json();
            const targetFile = files.find(f => f.id === fileDetails.fileId);
            return targetFile ? targetFile.has_password : true; // Assume password needed if file not found or error
        } catch {
            return true; // Assume password needed on error
        }
    }


    async function initiateDownload(password) {
        if (!fileToDownloadWithPassword) return;

        const { peerAddress, peerPort, fileId, fileName } = fileToDownloadWithPassword;
        const encodedPeerAddress = encodeURIComponent(peerAddress);
        // This is the backend endpoint that will proxy the P2P download
        const downloadUrl = `${API_BASE_URL}/peers/${encodedPeerAddress}/${peerPort}/download/${fileId}`;

        try {
            console.log(`Attempting to download ${fileName} from ${peerAddress}:${peerPort} (ID: ${fileId})`);
            const response = await fetch(downloadUrl, {
                method: 'POST', // POST to send password in body
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ password: password })
            });

            if (!response.ok) {
                const errorData = await response.json(); // Try to get error message from backend
                throw new Error(errorData.error || `Download failed: ${response.statusText} (Status: ${response.status})`);
            }

            // Handle successful download (file stream)
            const blob = await response.blob();
            const link = document.createElement('a');
            link.href = URL.createObjectURL(blob);
            link.download = fileName; // Set the default filename for the download
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            URL.revokeObjectURL(link.href); // Clean up

            console.log(`${fileName} download initiated.`);
            passwordPromptDiv.style.display = 'none';
            fileToDownloadWithPassword = null;

        } catch (error) {
            console.error('Error downloading file:', error);
            alert(`Download failed for ${fileName}: ${error.message}`);
            // Keep password prompt open if it was a password error, or hide if other error
            // For simplicity, just log and user can retry.
        }
    }

    console.log('P2P File Sharer App JS Loaded. Waiting for DOMContentLoaded.');
});
