# Reference — SDN-Controlled Private Tor Network

**INFORMATION-ORIENTED · FACTUAL · LOOKUP-DRIVEN**

---

## 1. Technology and Authoritative Sources

| Technology | Version Used | Official Source |

| :--- | :--- | :--- |

| **Mininet / Containernet** | Containernet `2.5.0` (commit `cc4cc08e7…`) | [Mininet Documentation](http://mininet.org/overview/) / [Containernet Repository](https://github.com/containernet/containernet) |

| **OS-Ken** | `2.14.0` (Ryu fork) | [OpenStack OS-Ken Documentation](https://docs.openstack.org/os-ken/latest/) |

| **Open vSwitch (OVS)** | `2.17.0` | [Open vSwitch Documentation](https://docs.openvswitch.org/) |

| **Tor** | `0.4.8.10` (via `antitree/private-tor:latest`) | [Tor Project Documentation](https://2019.www.torproject.org/docs/documentation.html.en) / [Tor Manual](https://2019.www.torproject.org/docs/tor-manual.html.en) |

| **NetworkX** | `3.6.1` | [NetworkX Documentation](https://networkx.org/documentation/stable/) |

| **Python** | `3.12.4` | [Python 3.12 Documentation](https://docs.python.org/3.12/) |

---

## 2. Project Environment

* **Operating System:** Ubuntu 22.04 LTS (Linux Kernel `6.5`)

* **Python Version:** `3.12.4`

* **Container Engine:** Docker Engine `24.0.6`

* **Container Image:** `antitree/private-tor:latest` (Tor `0.4.8.10` compiled with `libevent` and OpenSSL `3.0`)

* **Network Emulation Environment:** Containernet `2.5.0` (Mininet-compatible wrapper creating Docker containers as network hosts attached via `veth` pairs to OVS bridges)

* **Core Dependencies (pinned in `requirements.txt`):**

  * `os_ken`: `2.14.0`

  * `networkx`: `3.6.1`

  * `mininet` / `containernet`: `2.5.0`

  * `requests`: Pinned in `requirements.txt`

  * `pysocks`: Pinned in `requirements.txt`

  * `avro_logic.py`: Custom local Python module implementing MiniAVOA

---

## 3. Network Specification

### Topology Architecture

* **Fabric Type:** Leaf-Spine Data Center Topology

* **Subnet:** Isolated `172.18.0.0/16` (no NAT, masquerading, or external Internet routing; dummy default gateway set to `172.18.0.254`).

* **Auxiliary SDN Hosts:** `za_h1`, etc., attached to Leaf `s4` on subnet `10.0.0.x` (used by the SDN optimizer).

### Open vSwitch (OVS) Infrastructure (7 Switches)

* **Spine Switches (3):** `s1`, `s2`, `s3`

* **Leaf Switches (4):** `s4`, `s5`, `s6`, `s7`

* **Inter-Switch Connectivity:** Full-mesh interconnection between all leaf switches (`s4`–`s7`) and all spine switches (`s1`–`s3`).

### Tor Container Nodes (4 Nodes)

| Node Name | Docker Container Name | IP Address | Leaf Switch | Primary Role & Responsibilities |

| :--- | :--- | :--- | :--- | :--- |

| `tor_cli` | `mn.tor_cli` | `172.18.0.10/16` | `s5` | **Client (`AvroClient`):** Runs Tor client + local SOCKS5 proxy. Initiates circuits and forwards application traffic (`curl`, `requests`). |

| `tor_relay` | `mn.tor_relay` | `172.18.0.4/16` | `s6` | **Directory Authority + Relay (`AvroRelay`):** Sole Directory Authority (DA). Signs votes, publishes consensus, and acts as an onion relay. |

| `tor_relay2` | `mn.tor_relay2` | `172.18.0.6/16` | `s6` | **Relay (`AvroRelay2`):** Dedicated middle/exit relay providing a distinct circuit hop. |

| `tor_hsdir` | `mn.tor_hsdir` | `172.18.0.5/16` | `s7` | **HSDir + Relay (`AvroHSDir`):** Hidden-Service Directory storing HS descriptors; also operates as a relay and hosts internal HTTP test endpoints. |

### Link Configuration

* **Link Type:** Mininet/Containernet `TCLink`

* **Bandwidth:** `10 Mbps`

* **Propagation Delay:** `10 ms`

---

## 4. Port and Protocol Registry

| Service / Protocol | Port(s) | Transport | Bound IP / Scope | Description |

| :--- | :--- | :--- | :--- | :--- |

| **Tor SOCKS5 Proxy** | `9050` | TCP | `172.18.0.10:9050` (`tor_cli`) | Accepts local application connections (`curl`, `requests`) to route over Tor circuits. |

| **Tor Onion Router (ORPort)** | `7000` | TCP (TLS) | `172.18.0.4:7000`, `172.18.0.5:7000`, `172.18.0.6:7000` | Peer-to-peer TLS-encrypted onion routing and circuit cell forwarding. |

| **Tor Directory (DirPort)** | `9030` | TCP (HTTP) | `172.18.0.4:9030`, `172.18.0.5:9030`, `172.18.0.6:9030` | Serves network status consensus, authority certificates, votes, and router descriptors. |

| **Internal Test HTTP** | `80` | TCP (HTTP) | `172.18.0.5:80` (`tor_hsdir`) | Destination endpoint for circuit verification (e.g., `http://172.18.0.5:80/testfile`). |

| **OpenFlow Protocol** | Standard OVS/OpenFlow control channel | TCP | Loopback / Management bridge (`s1`–`s7` ↔ OS-Ken) | Southbound control plane between OVS switches (`2.17.0`) and `SuperAvroController` (OpenFlow `1.3` standard for OS-Ken). |

---

## 5. Controller Specification

* **Controller Class / Application:** `SuperAvroController`

* **Framework & Version:** OS-Ken `2.14.0`

* **Southbound Protocol:** OpenFlow (managed via OS-Ken `ofproto` / `ofp_event`)

* **Implemented Event Handlers:**

  * `OFPSwitchFeatures`: Registers OVS datapaths (`s1`–`s7`) into `self.datapaths` upon switch connection.

  * `packet_in` (ARP): Inspects incoming ARP packets to dynamically learn and map host `MAC ↔ IP` associations across all containers and hosts.

  * `packet_in` (IPv4): Triggers path computation via the `MiniAVOA` optimizer between source and destination leaf switches, then provisions flow rules along the computed path.

* **Topology Discovery Mechanism:** Switch registration via `OFPSwitchFeatures` combined with passive ARP snooping (`packet_in`) and NetworkX graph modeling (`3.6.1`) of the leaf-spine fabric.

* **Routing & Flow Installation Interfaces:**

  * **Interface:** `add_flow()` method invoked per switch along the calculated switch path.

  * **Match Fields:** `eth_type=0x0800` (IPv4), `ipv4_src`, `ipv4_dst`, `in_port`.

  * **Action:** `output=<port_to_next_switch>`.

  * **Payload Transparency:** Operates strictly on L2/L3 headers; encrypted Tor cells remain uninspected and unmodified.

---

## 6. Routing Optimizer Specification

* **Module Location:** `avro_logic.py`

* **Algorithm:** `MiniAVOA` (Genetic-algorithm / African Vultures Optimization-inspired path optimizer)

* **Population Size:** `30`

* **Epochs / Generations:** `50`

* **Link Weight Evaluation & Boundaries:** Evaluates underlying link metrics (latency and bandwidth across the `10 Mbps` / `10 ms` TCLinks) to determine optimal switch-to-switch traversal costs. *(Note: Explicit numeric min/max weight clamping constants and exact mathematical fitness formula expressions are encapsulated within `avro_logic.py` and not exposed in the high-level architecture snapshot.)*

* **Fitness Function:** Evaluates candidate switch-level paths across the leaf-spine graph based on link weights (minimizing latency / maximizing available bandwidth).

* **Return Values & Behavior:**

  * Returns an ordered list of OVS switches representing the optimal path from source leaf switch to destination leaf switch.

  * The controller translates this switch sequence into hop-by-hop OpenFlow rules via `add_flow()`.

  * **Fallback / Isolation:** Operates strictly on the physical OVS underlay; does not alter Tor's internal 3-hop circuit selection (`Guard → Middle → Exit`).

---

## 7. Configuration Inventory

| File / Directory Path | Scope / Component | Purpose & Relevant Configuration Keys / Values |

| :--- | :--- | :--- |

| `topo.py` | Host / Containernet | Defines the 7-switch leaf-spine topology, `TCLink(bw=10, delay='10ms')`, static IP mappings (`tor_configs`), gateway assignment (`172.18.0.254`), and runs `fix_host_key_ownership()` prior to container boot. |

| `avro_logic.py` | Host / SDN Controller | Implements the `MiniAVOA` routing optimizer (`population = 30`, `generations = 50`). |

| `requirements.txt` | Host / Python Env | Pins Python dependencies (`requests`, `pysocks`, `networkx==3.6.1`, `mininet`, `os_ken==2.14.0`). |

| `/etc/tor/torrc` *(Common across all Tor containers)* | All Tor Nodes | `TestingTorNetwork 1`, `User root`, `DataDirectory /var/lib/tor`, `RunAsDaemon 1`, `Log notice file /etc/tor/tor.log`, `AssumeReachable 1`, `EnforceDistinctSubnets 0`, `ExitPolicy accept *:*`, `ExtendAllowPrivateAddresses 1`, `DirAuthority AvroRelay orport=7000 v3ident=… 172.18.0.4:9030 EE242EF...` |

| `/etc/tor/torrc` (`tor_cli`) | Client Container | `Nickname AvroClient`, `Address 172.18.0.10`, `SocksPort 172.18.0.10:9050`, `UseMicrodescriptors 0` |

| `/etc/tor/torrc` (`tor_relay`) | DA + Relay Container | `Nickname AvroRelay`, `Address 172.18.0.4`, `ORPort 172.18.0.4:7000`, `DirPort 172.18.0.4:9030`, `AuthoritativeDirectory 1`, `V3AuthoritativeDirectory 1`, `TestingDirAuthVoteExit *`, `TestingDirAuthVoteGuard *`, `TestingDirAuthVoteHSDir *`, `KeyDirectory /etc/tor/keys` |

| `/etc/tor/torrc` (`tor_relay2`) | Relay Container | `Nickname AvroRelay2`, `Address 172.18.0.6`, `ORPort 172.18.0.6:7000`, `DirPort 172.18.0.6:9030` |

| `/etc/tor/torrc` (`tor_hsdir`) | HSDir + Relay Container | `Nickname AvroHSDir`, `Address 172.18.0.5`, `ORPort 172.18.0.5:7000`, `DirPort 172.18.0.5:9030` |

| `configs/*/keys` → `/etc/tor/keys` | Host → Container Mount | Stores node cryptographic keys (`secret_id_key`, `secret_onion_key`, v3 identity certificates); chowned to `root` by `topo.py`. |

| `/var/lib/tor` | Inside Containers | Runtime Tor data directory storing cached consensus, descriptors, and state. |

| `/etc/tor/tor.log` | Inside Containers | Runtime notice-level log file tracking bootstrap milestones (`0%` to `100%`). |
