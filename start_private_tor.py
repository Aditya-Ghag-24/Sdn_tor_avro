import os
import subprocess

# Define your mapping of Chutney nodes to Mininet Hosts
# Format: { "chutney_folder": ("mininet_host", "ip_address") }
mapping = {
    "000a": ("za_h1", "10.0.1.1"),
    "001a": ("zb_h1", "10.0.2.1"),
    "002a": ("za_h2", "10.0.1.2"),
    "003r": ("zb_h2", "10.0.2.2"),
}

def setup_tor():
    print("--- Starting Private Tor Bridge for AVRO SDN ---")
    
    # 1. Kill old Tor processes
    subprocess.run(["sudo", "pkill", "-9", "tor"])
    
    for node, (host, ip) in mapping.items():
        torrc_path = f"/home/vboxuser/chutney/net/nodes/{node}/torrc"
        
        # 2. Automatically fix the IP inside the torrc
        if os.path.exists(torrc_path):
            with open(torrc_path, 'r') as f:
                content = f.read()
            
            # Replace localhost with the actual Mininet IP for this host
            content = content.replace("Address 127.0.0.1", f"Address {ip}")
            # Replace any other 127.0.0.1 (like DirAuthorities) with the gateway or peer IPs
            # (Simplification: for PoC, we point DirAuths to the first two hosts)
            content = content.replace("127.0.0.1:5000", "10.0.1.1:5000")
            content = content.replace("127.0.0.1:5001", "10.0.2.1:5001")

            with open(torrc_path, 'w') as f:
                f.write(content)
            
            # 3. Launch the Tor process inside the Mininet namespace
            print(f"Launching Tor on {host} ({ip}) using config {node}...")
            cmd = f"sudo ip netns exec mininet-{host} tor -f {torrc_path} --RunAsDaemon 1"
            subprocess.run(cmd, shell=True)

if __name__ == "__main__":
    setup_tor()
