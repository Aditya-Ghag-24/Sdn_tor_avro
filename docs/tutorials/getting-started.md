# Getting Started

Set up, run, and verify the SDN-controlled private Tor network.

By the end of this tutorial, you will have:
* Deployed an isolated Containernet topology with Open vSwitch.
* Initialized an active OSKen OpenFlow 1.3 controller.
* Booted containerized Tor relays and clients.
* Executed the `MiniAVOA` algorithm to dynamically balance edge metrics and route Tor traffic.

---

## Prerequisites

Verify your host environment meets the following specifications before proceeding:

* **OS:** Ubuntu 20.04 or 22.04 LTS (x86_64).
* **System Utilities:** Docker Engine (`docker-ce`), Open vSwitch (`openvswitch-switch`), Git, Python 3.8+.
* **Emulation Engine:** [Containernet](https://github.com/containernet/containernet) installed and built on your host.
* **Privileges:** `sudo` access.

---

## Environment Setup

### 1. Clone the Repository
Download the project source and enter the root directory:
```bash
git clone https://github.com/Aditya-Ghag-24/Sdn_tor_avro.git
cd Sdn_tor_avro
```

2. Configure Virtual Environment & Install Dependencies

Create an isolated Python environment and install core controller libraries:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Verification: Confirm packages are installed:
```bash
python3 -c "import os_ken, networkx, numpy; print('Environment Ready')"
```
Expected output: Environment Ready


Project Configuration

Inspect and confirm baseline configuration files before execution:

    Topology Map: Verify relay, switch, and host definitions in topo.py.

    Tor Daemon Configs: Confirm port bindings (ORPort, DirPort) in configs/.

    Controller Settings: Review default AVOA population size and epoch counts in super_controller.py.

(For parameter descriptions and configuration file options, see the Configuration Reference.)


Running the Project

Launch the components in the required order across two separate terminal sessions.
Step 1: Launch the SDN Controller

Open Terminal 1, activate your virtual environment, and start the OSKen controller:
```bash
source venv/bin/activate
osken-manager super_controller.py
```
Expected output:
```text
loading app super_controller.py
loading app os_ken.controller.ofp_handler
instantiating app super_controller.py of SuperAvroController
instantiating app os_ken.controller.ofp_handler of OFPHandler
```
Step 2: Deploy the Containernet Topology

Open Terminal 2 and start the network topology with administrative privileges:
```bash
sudo python3 topo.py
```
Expected output: Containernet creates OVS bridges, spins up Docker Tor containers, and establishes OpenFlow channel connections to 127.0.0.1:6653.
Verify Your Installation

Run these checks to confirm the controller, switches, and Tor overlay are communicating correctly.
1. Confirm OpenFlow Bridge Connections

In  a third terminal, query Open vSwitch to verify active bridge attachments:
```bash
sudo ovs-vsctl show
```
Verification: Output displays active bridges (s1, s2, etc.) with is_connected: true pointing to Controller tcp:127.0.0.1:6653.

In the same terminal, query open switch to check active connection with controller
```bash
sudo ovs-vsctl list Controller
```
Verification: look for is_connected true
 
2. Verify Tor Daemon Processes

Inspect the running Docker containers managed by Containernet:
```bash
sudo docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

3. Verify Tor bootstrap Status
```bash
containernet> tor_cli cat /etc/tor/tor.log | tail -n 10
```

Expected output: In the end it will say Bootstrapped 100% 

4. Trigger Routing Optimization & Test Connectivity

Send a test ping or HTTP request from the client node through the network:

# In the Containernet CLI prompt:
```bash
containernet>  tor_cli ping -c 3 172.18.0.4
```

Verification: Look at Terminal 1 (running super_controller.py). You should see log lines indicating that MiniAVOAresolved candidate edge weights and installed corresponding flow entries on the switches.
Clean Up

When finished testing, shut down the emulated environment to free system interfaces:

# Exit the Containernet CLI:
```bash
containernet> exit
```
# Clear virtual links and residual Open vSwitch ports:
```bash
sudo mn -c
```
