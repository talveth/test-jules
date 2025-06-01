# LAN File Sharer

A peer-to-peer file sharing application for local area networks.

## Usage

1.  Ensure Python 3.x is installed.
2.  Install dependencies: `pip install -r requirements.txt` (You may need to create this file if it's missing and list dependencies like Flask).
3.  Run the application: `python -m lan_file_sharer.p2p_app.main`
4.  Enter a username when prompted.
5.  The application will discover other peers on the network and allow file sharing.

## Network Configuration

**Firewall Configuration:** For peer discovery to work correctly, ensure your system's firewall allows incoming and outgoing UDP traffic on port 19000 (or the configured `MULTICAST_PORT`). If instances cannot find each other, a firewall is a common cause.
