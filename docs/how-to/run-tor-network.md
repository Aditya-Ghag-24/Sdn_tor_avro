# Run the Private Tor Network

Manage, interact with, and verify containerized private Tor nodes across the Containernet data plane.

> ⚠️ **ISOLATED TESTBED ENVIRONMENT**
> This deployment operates inside a strictly isolated virtual network with no external DNS or Internet routing. Containers mount to Open vSwitch datapath ports rather than the standard `docker0` bridge; therefore, `docker inspect` will not return standard host bridge IP allocations.

---

## Architecture & Environment Constraints

Review these architectural constraints before executing commands against the testbed:

* **Container Lifecycle & Ephemeral State:** Node containers (`mn.tor_cli`, `mn.tor_hsdir`, `mn.tor_relay`, `mn.tor_relay2`) are bound directly to the runtime lifetime of `topo.py`. Terminating the script or exiting the `containernet>` prompt tears down all containers, virtual ethernet interfaces, and OVS bridge attachments. Keep `topo.py` active in a dedicated terminal during all testing sessions.
* **Minimal Base Image Environment:** Nodes run `antitree/private-tor` (Debian Jessie minimal base). The containers do not include `python3`, `curl`, `stem`, or `tor-prompt`. 
* **Air-Gapped Package Management:** `apt-get` commands will fail at runtime because upstream Debian Jessie mirrors are unreachable from the isolated virtual network.

---

## Container Reference & Mount Points

Containernet automatically prefixes container handles with `mn.`:

| Node Role | Containernet CLI Target | Docker Name | Mounted Config Path | Configured Ports |
| :--- | :--- | :--- | :--- | :--- |
| **Tor Client** | `tor_cli` | `mn.tor_cli` | `configs/client/` | `SOCKSPort 9050` |
| **Directory Authority** | `tor_hsdir` | `mn.tor_hsdir` | `configs/hsdir/` | `ORPort 7000`, `DirPort 9030` |
| **Relay 1** | `tor_relay` | `mn.tor_relay` | `configs/relay1/` | `ORPort 7000`, `DirPort 9030` |
| **Relay 2** | `tor_relay2` | `mn.tor_relay2` | `configs/relay2/` | `ORPort 7000`, `DirPort 9030` |

---

## Starting the Topology

### 1. Launch Containernet
Execute the topology builder with administrative privileges in Terminal 1:
```bash
sudo python3 topo.py
```
Verification: The script completes OVS switch provisioning, calls net.start(), and presents the interactive prompt:
Plaintext
```text
containernet>
```
Leave this process running.
## Inspecting Bootstrap Status

Confirm nodes have completed consensus negotiation and reach 100% bootstrap status.
### Method A: Query via Host Volume Mappings (Recommended)

Inspect the persistent log streams directly from your host terminal without entering container namespaces:
Bash
```bash
# Check client bootstrap state:
grep -i "bootstrapped" configs/client/tor.log

# Stream directory authority events:
tail -f configs/hsdir/tor.log
```
Verification: Confirm the log terminates with:
```text
[notice] Bootstrapped 100% (done): Done
```
### Method B: Query via Docker CLI

Read the mounted log file via container execution:
Bash
```bash
sudo docker exec mn.tor_cli grep -i "bootstrapped" /etc/tor/tor.log
```
## Interacting with the Isolated Network

Because third-party utilities are omitted from the minimal image, interact with node ports (9050, 9030, 7000) using one of these three workflows:
# Workflow 1: Execute Native Commands from Containernet CLI

Run commands directly inside a target container's network namespace via the active containernet> prompt:
```text
# Check internal interface IP and link states:
containernet> tor_cli ifconfig

# Test basic ICMP reachability to the directory authority:
containernet> tor_cli ping -c 3 172.18.0.5
```
# Workflow 2: Probe Ports via Native Bash TCP Streams

Verify the Tor SOCKS proxy listener (127.0.0.1:9050) using built-in Bash socket redirection (does not require curl or netcat):
```Bash
sudo docker exec mn.tor_cli /bin/bash -c "exec 3<>/dev/tcp/127.0.0.1/9050 && echo 'Socket 9050 Open' && exec 3<&-"
```
Verification: Prints Socket 9050 Open if the local Tor daemon is actively listening.

# Workflow 3: Query SOCKS Listener via Pre-installed Python 2.7

Check if the base Debian image exposes a legacy Python runtime:
```Bash
sudo docker exec mn.tor_cli python -c "
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
result = s.connect_ex(('127.0.0.1', 9050))
print('Port 9050 reachable' if result == 0 else 'Port unreachable')
s.close()
"
```
## Modifying Node Binaries (Optional Dockerfile Rebuild)

To permanently bake utilities (curl, python3, stem) into the testbed images without needing runtime internet access:

1. Create an updated Dockerfile:
 ```Dockerfile

    FROM antitree/private-tor:latest
    RUN sed -i s/deb.debian.org/archive.debian.org/g /etc/apt/sources.list && \
        sed -i 's|security.debian.org|archive.debian.org/debian-security/|g' /etc/apt/sources.list && \
        sed -i '/jessie-updates/d' /etc/apt/sources.list && \
        apt-get -o Acquire::Check-Valid-Until=false update && \
        apt-get install -y --no-install-recommends curl net-tools && \
        rm -rf /var/lib/apt/lists/*
```
2. Build and tag locally:
``` Bash

    sudo docker build -t local/private-tor:tools .
```
3. Update topo.py: Update the image reference inside topo.py from antitree/private-tor:latest to local/private-tor:tools.

## Stopping and Cleaning the Network
1. Exit the Containernet Session

Exit cleanly from the prompt:
```text

containernet> exit
```
2. Clear Residual Kernel Namespaces & Bridges

Reset Open vSwitch datapath allocations and remove unlinked virtual interfaces:
```Bash

sudo mn -c
```
Verification: Confirm all transient OVS bridges are unlinked:
```Bash

sudo ovs-vsctl show
```

