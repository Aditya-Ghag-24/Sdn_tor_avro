# Launch the SDN Controller

Initialize, configure, and verify the OSKen OpenFlow 1.3 control plane and the `MiniAVOA` routing application.

---

## Overview

The SDN controller operates as the central brain of the network. It manages topology discovery, listens for OpenFlow handshake events from Open vSwitch (OVS), runs `MiniAVOA` to optimize path edge weights, and proactively installs flow table modifications (`flow_mod`).

---

## Prerequisites

Confirm these conditions prior to launching the controller:

* **Python Virtual Environment:** Ensure dependencies from `requirements.txt` (`os-ken`, `networkx`, `numpy`) are installed inside your virtual environment.
* **Port Availability:** Ensure TCP ports `6633` and `6653` (OpenFlow protocol ports) are not occupied by lingering processes.
* **Launch Order:** Start the controller **before** launching `topo.py`. If the topology boots without an active controller, switches will fail to register their datapath features.

---

## Port & Process Pre-Flight Check

Check if OpenFlow ports `6633` or `6653` are already bound by an existing controller or zombie process:

```bash
sudo ss -tulpn | grep -E ':6633|:6653'
```
If a process is holding either port, terminate it:
```Bash

sudo fuser -k 6633/tcp 6653/tcp
```
Verification: Re-run sudo ss -tulpn | grep -E ':6633|:6653'. The command should return clean with no output.
### Initializing the Controller

1. Activate Environment and Start OSKen

Run the controller in Terminal 1 using osken-manager:
```Bash

cd ~/tor_avro
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
> Note on Eventlet Warning: If you see 1 RLock(s) were not greened, to fix this error make sure you run eventlet.monkey_patch() before importing any other modules., this is an upstream Eventlet threading notice and does not affect OpenFlow operations.

2. Run with Verbose OpenFlow Logging (Recommended for Debugging)

Launch with --verbose to inspect OpenFlow brick registrations, socket connections, and real-time PacketIn routing calculations:

```Bash

osken-manager --verbose super_controller.py
```
Expected verbose startup output:
```text

BRICK SuperAvroController
  CONSUMES EventOFPPacketIn
  CONSUMES EventOFPSwitchFeatures
BRICK ofp_event
  PROVIDES EventOFPPacketIn TO {'SuperAvroController': {'main'}}
  PROVIDES EventOFPSwitchFeatures TO {'SuperAvroController': {'config'}}
```
Verifying Controller Operation

Perform these checks in a separate terminal while super_controller.py runs.

1. Verify Active TCP Listeners

Confirm that OSKen is actively listening for incoming switch connections on ports 6633 and 6653:

```Bash

ss -tln | grep -E '6633|6653'
```
Expected output:
```text

LISTEN   0   50   0.0.0.0:6633   0.0.0.0:*
LISTEN   0   50   0.0.0.0:6653   0.0.0.0:*
```
2. Verify Open vSwitch Handshake

Launch the topology in Terminal 2 (sudo python3 topo.py). When running with --verbose, Terminal 1 logs the OpenFlow socket handshakes and datapath IDs:

Expected verbose controller handshake logs:
```text

connected socket:<eventlet.greenio.base.GreenSocket object at 0x...> address:('127.0.0.1', 60386)
hello ev <os_ken.controller.ofp_event.EventOFPHello object at 0x...>
move onto config mode
EVENT ofp_event->SuperAvroController EventOFPSwitchFeatures
switch features ev version=0x4,msg_type=0x6,msg_len=0x20,xid=0x...,OFPSwitchFeatures(auxiliary_id=0,capabilities=79,datapath_id=1,n_buffers=0,n_tables=254)
move onto main mode
```
Confirm the connection status directly on Open vSwitch:
```Bash

sudo ovs-vsctl show
```
Expected output: Under each bridge (s1, s4, etc.), confirm is_connected: true pointing to tcp:127.0.0.1:6633:

```text

    Bridge s1
        Controller "tcp:127.0.0.1:6633"
            is_connected: true
        fail_mode: secure
```
3. Verify Dynamic Route Calculation (MiniAVOA)

As Tor relays bootstrap or test traffic traverses the network, Terminal 1 logs incoming packet events and dynamic AVRO path computations:

Expected controller routing logs:
```text

EVENT ofp_event->SuperAvroController EventOFPPacketIn
-- AVRO (Refresh): Routing 172.18.0.6 -> 172.18.0.10 via [6, 1, 5] --
EVENT ofp_event->SuperAvroController EventOFPPacketIn
-- AVRO (Refresh): Routing 172.18.0.10 -> 172.18.0.6 via [5, 3, 6] --
```
(The bracketed numbers [6, 1, 5] represent the optimal sequence of OpenFlow switch Datapath IDs resolved by MiniAVOA.)

### Runtime Flow Inspection

Inspect the forwarding rules installed on the switches by the controller.
1. Dump Flow Tables for a Switch

Query OpenFlow 1.3 rules directly from switch s1:
```Bash

sudo ovs-ofctl -O OpenFlow13 dump-flows s1
```
Expected output format:
```text

cookie=0x0, duration=14.2s, table=0, n_packets=8, n_bytes=672, priority=1,in_port=1,dl_dst=... actions=output:2
cookie=0x0, duration=60.0s, table=0, n_packets=12, n_bytes=1008, priority=0 actions=CONTROLLER:65535
```
Key fields to check:

    priority=0 actions=CONTROLLER:65535: Default table-miss flow forwarding unmatched packets to super_controller.py.

    priority=1 ... actions=output:X: Active unicast paths installed dynamically by MiniAVOA.

    n_packets > 0: Confirms packets are traversing the installed switch rules.

### Troubleshooting

* Address already in use (Errno 98):
Another OSKen instance is running in the background. Kill any processes bound to OpenFlow ports:
```Bash

    sudo fuser -k 6633/tcp 6653/tcp
```
    Switches show is_connected: false:

        1. Check if the controller stopped or exited in Terminal 1.

        2. Confirm local firewall rules are not blocking loopback traffic on ports 6633 and 6653:
```Bash

sudo ufw status
```
* Fallback Warning in Logs ([AVRO ERROR] Custom AVOA failed):

* If graph dimensions change unexpectedly or MiniAVOA encounters a runtime error, the controller assigns default uniform weights (1.0) and computes standard Dijkstra shortest paths as a failsafe without dropping traffic.

### Stopping the Controller

To gracefully shut down the controller:

1. Navigate to the terminal running osken-manager.

2. Press Ctrl + C (outputs Keyboard Interrupt received. Closing OSKen application manager...).

Confirm socket shutdown:
```Bash

    sudo ss -tulpn | grep -E ':6633|:6653'
```
