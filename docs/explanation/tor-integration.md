# Tor Integration

## 1. Overview

This document describes the integration of a private Tor network within the SDN-controlled testbed. The Tor environment consists of containerized Tor nodes deployed through Containernet and interconnected using an Open vSwitch (OVS) Spine-Leaf topology.

The implementation uses four Tor containers:
* A Tor client.
* Two Tor relay nodes.
* A directory authority, implemented by the first relay.

The SDN infrastructure provides the underlying network connectivity, while the OS-Ken controller manages packet forwarding using the `MiniAVOA` routing mechanism. The deployment operates as an isolated test environment without external Internet connectivity.

---

## 2. Tor Network Architecture

### 2.1 Components and Responsibilities

The private Tor network consists of the following nodes:

| Container | Tor Nickname | IP Address | Role |
| :--- | :--- | :--- | :--- |
| `tor_cli` | `AvroClient` | `172.18.0.10` | Tor client |
| `tor_relay` | `AvroRelay` | `172.18.0.4` | Tor relay and directory authority |
| `tor_relay2` | `AvroRelay2` | `172.18.0.6` | Second Tor relay |
| `tor_hsdir` | `AvroHSDir` | `172.18.0.5` | Hidden-service directory relay |

* **Tor Client (`tor_cli`):** Initiates communication through the private Tor network. It obtains directory information from the configured directory authority and uses the available relay information to construct Tor circuits.
* **Directory Authority (`tor_relay`):** The first relay also performs the directory authority role. It is configured with `AuthoritativeDirectory 1` and `V3AuthoritativeDirectory 1`. It provides directory information and participates in the private network's consensus generation.
* **Second Relay (`tor_relay2`):** Provides an additional relay node within the private network. It is configured as a regular relay and does not perform the directory authority role.
* **Hidden-Service Directory (`tor_hsdir`):** Configured as a hidden-service directory relay. It is distinct from the directory authority and is not responsible for generating the network consensus.

### 2.2 Network Interconnection

All four Tor containers are connected to the same OVS fabric through the Containernet Spine-Leaf topology. Their switch attachments are:

| Tor Node | Connected Switch | Port |
| :--- | :--- | :--- |
| `tor_cli` | `s5` | `9` |
| `tor_relay` | `s6` | `9` |
| `tor_relay2` | `s6` | `10` |
| `tor_hsdir` | `s7` | `9` |

The spine switches (`s1`–`s3`) provide interconnection between the leaf switches (`s4`–`s7`), allowing the Tor containers to communicate across the emulated network.

---

## 3. Private Tor Network Configuration

### 3.1 Configuration Files

Each Tor container uses an individual configuration directory mounted from the host:

```text
configs/
├── client/
│   └── torrc
├── relay/
│   └── torrc
├── relay2/
│   └── torrc
└── hsdir/
    └── torrc
```
The configuration files define the identity, network addresses, listening ports, directory settings, and logging behaviour of each Tor instance. The nodes use the antitree/private-tor:latest Docker image.
### 3.2 Client Configuration

The client configuration includes the following important parameters:
| Parameter | Purpose |
| :--- | :--- | :--- |
| TestingTorNetwork 1 |	Enables Tor's private testing-network configuration |
| Nickname AvroClient |	Identifies the client |
| Address 172.18.0.10 |	Defines the client's network address |
| SocksPort 172.18.0.10:9050 |	Exposes the SOCKS proxy |
| DataDirectory /var/lib/tor |	Stores Tor runtime data |
| Log notice file /etc/tor/tor.log |	Writes Tor logs to a file |
| DirAuthority | Identifies the private directory authority |

The client is configured to trust the directory authority hosted by tor_relay at 172.18.0.4:9030.
### 3.3 Relay Configuration

The first relay (tor_relay) has the following important settings:

    * ORPort 172.18.0.4:7000

    * DirPort 172.18.0.4:9030

    * AuthoritativeDirectory 1

    * V3AuthoritativeDirectory 1

    * ExitPolicy accept *:*

    * ExtendAllowPrivateAddresses 1

It also contains directory-authority voting configuration for the private test network.

The second relay (tor_relay2) uses a similar relay configuration but does not have the authoritative-directory flags. The tor_hsdir node is configured as a regular relay with hidden-service directory functionality.
### 3.4 Port Configuration

The implementation uses the following ports:
|Port |	Component | Purpose |
| :--- | :--- | :--- |
| 9050 | SOCKSPort | Client SOCKS proxy |
| 7000 | ORPort	| Tor relay communication |
| 9030 | DirPort | Directory information service |

The SOCKS proxy is exposed by the client, while the relay nodes expose their ORPort and DirPort services.
### 3.5 Relay Identity and Key Management

Tor relay identities and cryptographic keys are stored under /etc/tor/keys. These directories are mounted from the host into their respective containers.

Before the network starts, setup_network() performs ownership and permission adjustments:
```Bash

chown root:root
chmod 700
```
This ensures that Tor can access its key directories using the configured runtime user. The directory authority's v3 identity fingerprint is specified in the DirAuthority configuration entries across the nodes, allowing them to identify and trust the same authority.
### 3.6 Relay Discovery

The client discovers available relays through the configured directory authority. The process follows these steps:

    1. The client reads its torrc configuration and identifies AvroRelay as its directory authority.

    2. It contacts the authority at 172.18.0.4:9030.

    3. The authority provides the network consensus and relay descriptors.

    4. The client obtains the available relay addresses and ORPort information.

    5. The client uses this information when constructing Tor circuits.

This allows the client to discover the available relays without relying on the public Tor directory infrastructure.
## 4. Containerization and Network Integration
### 4.1 Docker-Based Deployment

Docker is used to deploy independent Tor instances within the testbed. Each container maintains its own:

    * Tor process.

    * Configuration files.

    * Cryptographic keys.

    * Runtime data.

    * Log files.

The use of Docker allows each Tor node to operate independently while sharing the underlying emulated network infrastructure. Configuration directories are bind-mounted from the host into /etc/tor inside their respective containers.
### 4.2 Containernet and Open vSwitch Integration

Containernet extends Mininet by allowing Docker containers to operate as network hosts. The Tor containers are created using:
```Python

network_mode='none'
```
This prevents Docker from automatically attaching them to its default bridge network. Instead, Containernet connects the containers directly to the OVS switches defined in topo.py. The resulting network allows the Tor nodes to communicate through the same infrastructure managed by the SDN controller.
### 4.3 IP Addressing

The implementation uses two distinct addressing ranges:
| Address Range | Purpose |
| :--- | :--- |
| 10.0.0.0/8 | Internal Mininet addressing |
| 172.18.0.0/16 | Private Tor network addressing |

After the containers are created, setup_network() configures their interfaces and assigns the corresponding Tor addresses. The configuration process includes:
```Bash

ip addr flush dev eth0
ip addr add 172.18.0.X/16 dev eth0
ip link set eth0 up
ip route add default via 172.18.0.254 dev eth0
```
Here, X represents the address assigned to the respective Tor node. The second address range is used to distinguish Tor container addressing from the standard Mininet host addressing.
### 4.4 Isolation from the Public Internet

The private Tor testbed does not have an external Internet connection configured. The containers are not attached to the standard Docker bridge, and no NAT or masquerading rules are configured to provide external connectivity. Their communication is restricted to the emulated network infrastructure. Consequently, the testbed is intended for internal experimentation rather than communication with the public Tor network.
## 5. Tor Bootstrap and Circuit Establishment
### 5.1 Bootstrap Process

When the Tor client starts, it must obtain the necessary directory information and establish a circuit before it can handle client streams. The initialization process involves:

    1. Reading the client configuration.

    2. Contacting the configured directory authority.

    3. Obtaining the network consensus.

    4. Downloading relay descriptors.

    5. Learning available relay information.

    6. Establishing connections with the selected relays.

    7. Completing circuit construction.

The Tor daemon reports its progress through bootstrap status messages.
### 5.2 Bootstrap Verification

In the current testbed, Tor initialization typically takes approximately 3–10 seconds. The client log can be inspected using:
```text

tor_cli cat /etc/tor/tor.log | tail -n 10
```
A successful initialization produces messages similar to:
```text

Tor has successfully opened a circuit.
Looks like client functionality is working.
Bootstrapped 100%: Done

The Bootstrapped 100% (done): Done message indicates that the client has completed its bootstrap process. The circuit-establishment message provides additional confirmation that the client has successfully opened a Tor circuit within the private network. The exact relay sequence should be verified separately using circuit-specific log entries if the individual circuit hops need to be documented.
```
## 6. Interaction Between Tor and SDN

The integration combines two independent mechanisms: Tor's circuit-based communication and SDN's control over the underlying network forwarding.
### 6.1 Tor Traffic Forwarding

Tor establishes connections between its client and relay nodes using its own protocol. These connections travel through the OVS infrastructure. The switches forward packets based on their installed forwarding rules, while the Tor processes manage circuit construction, relay communication, and encryption.
### 6.2 OS-Ken Controller

The OS-Ken controller operates as the central SDN control component. It communicates with the OVS switches using OpenFlow and receives network events from them. The controller manages forwarding decisions by installing and updating flow entries. Its role is to manage the underlying packet forwarding rather than modify Tor's internal circuit construction.
### 6.3 MiniAVOA Routing

MiniAVOA operates within the SDN controller and computes network paths for traffic flows. According to the current implementation, it handles traffic between the Tor containers as well as the standard Z-group Mininet hosts:

    * za_h1–za_h5

    * zb_h1–zb_h5

    * zc_h1–zc_h5

The algorithm determines the underlying switch paths and the controller installs the corresponding OpenFlow rules. It does not select Tor's entry, middle, or exit relays.
### 6.4 Coexistence of Tor Encryption and SDN Forwarding

Tor and SDN operate at different levels of the network. Tor provides its circuit-based communication and layered encryption, while SDN controls how packets traverse the underlying network infrastructure. The SDN controller can make forwarding decisions using network information and packet metadata without needing to decrypt Tor's encrypted relay traffic. The two mechanisms therefore coexist without MiniAVOA modifying Tor's internal encryption or relay-selection mechanisms.
## 7. Limitations of the Testbed

The private Tor deployment provides an experimental environment for investigating the interaction between Tor and SDN. However, it does not reproduce all the properties of the public Tor network.

The current limitations include:

    * Single Directory Authority: The testbed uses one directory authority, implemented by tor_relay. It does not reproduce the distributed directory-authority voting infrastructure of the public Tor network.

    * No Public Internet Exit Connectivity: Although the relay configuration includes ExitPolicy accept *:*, the testbed does not provide external Internet connectivity. Consequently, the relays cannot provide ordinary public Internet exit traffic.

    * Limited Hidden-Service Functionality: The tor_hsdir node is configured for hidden-service directory functionality, but the testbed does not establish externally accessible hidden services.

    * Limited Application-Level Verification: The current demonstration verifies successful Tor circuit establishment through the bootstrap logs. It does not independently demonstrate end-to-end application data transfer through a Tor circuit.

    * Limited Anonymity Evaluation: All nodes operate within a controlled laboratory environment. The implementation does not establish or measure real-world anonymity guarantees, traffic-analysis resistance, or path diversity across independent networks.

    * Limited Scalability: The current deployment contains two relay nodes and one additional HSDir node. It does not reproduce the scale or geographical distribution of the public Tor network.

    * Limited Performance Benchmarking: The current implementation records basic Tor logs but does not include systematic application-level bandwidth or latency benchmarking of Tor circuits.
