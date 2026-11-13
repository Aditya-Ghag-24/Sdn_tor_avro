# SDN-Controlled Private Tor Network with AVRO Routing

A proof-of-concept integrating the **African Vulture Optimization Algorithm (AVOA / AVRO)** into an **OSKen-based Software Defined Network (SDN)** to dynamically balance network-layer forwarding paths for a private Tor overlay network.

---

## Architecture

![SDN-Based Private Tor Network with AVRO Routing](docs/images/architecture.png)

The system isolates control, data forwarding, and application overlay operations across three tiers:

* **Application Layer (Tor Overlay):** Private Tor deployment (Directory Authorities, Guard Relays, Middle Relays, Exit Relays, and Clients) running as isolated container instances.
* **Control Layer (OSKen Controller with AVRO Engine):** Centralized control plane that discovers network topology, calculates candidate edge weights via metaheuristic optimization, and installs OpenFlow forwarding rules.
* **Infrastructure Layer (Data Plane):** Open vSwitch (OVS) nodes that forward encapsulated onion-routed traffic based on active flow table matches.

---

## Key Features

* **Private Tor Deployment:** Fully self-contained, isolated onion-routing network running without contact with the public Tor network.
* **Programmable Control Plane:** Built on the modern OSKen OpenFlow 1.3 controller engine.
* **Metaheuristic Dynamic Routing:** Adapts the African Vulture Optimization Algorithm (`MiniAVOA`) to balance edge metrics and avoid structural bottlenecks.
* **Decoupled Architecture:** Optimizes underlying layer-3 forwarding paths without decrypting cells or altering Tor’s application-layer anonymity invariants.
* **Containerized Emulation:** Reproducible virtual topology orchestration powered by Containernet and Open vSwitch.

---

## Technologies Used

* **Network Control & Emulation:** [OSKen](https://github.com/os-ken/os-ken) (OpenFlow 1.3 Controller), [Containernet](https://github.com/containernet/containernet), [Mininet](http://mininet.org/), [Open vSwitch](https://www.openvswitch.org/).
* **Privacy & Overlay Routing:** [Tor](https://www.torproject.org/) (Private directory authority, guard, relay, and client containers).
* **Graph & Numerical Computation:** [Python 3](https://www.python.org/), [NetworkX](https://networkx.org/) (Topology graphs & Dijkstra shortest path), [NumPy](https://numpy.org/) (Vector operations and fitness distribution evaluation).
* **Virtualization & Host Environment:** [Docker Engine](https://www.docker.com/), Ubuntu Linux.

---

## Routing Methodology (Overview)

Rather than using computationally intensive Deep Reinforcement Learning (DRL) or static Dijkstra shortest paths, the control layer employs an adapted variant of the African Vulture Optimization Algorithm (`MiniAVOA`).

1. **Topology Ingestion:** The controller models the switch interconnections as an undirected graph using NetworkX.
2. **Population-Based Search:** A population of candidate solution vectors (edge weight allocations) is initialized.
3. **Fitness Calculation:** Candidates are evaluated using statistical variance and mean edge distribution to prevent over-saturating specific transit links.
4. **Adaptive Phase Shift:** An exploration/exploitation decay factor controls whether the algorithm searches untested weight configurations or refines known optimal link distributions.
5. **Flow Rule Installation:** The optimal weight vector is mapped to the graph, shortest paths are calculated, and corresponding OpenFlow `flow_mod` entries are pushed to OVS switches.

For detailed algorithmic proofs, fitness formulas, and parameter comparisons with literature, see the [Routing Methodology Explanation](docs/explanation/routing-methodology.md) and [Algorithm Reference](docs/reference/algorithm.md).

---

## Current Limitations

* **Synthetic Metric Optimization:** Candidate fitness is currently computed over internal statistical representations of the link weights rather than dynamic OpenFlow port counters (`OFPPortStatsReply`).
* **Static Graph State:** Does not account for sudden runtime link failures (flapping) or external cross-traffic injection.
* **Unified Exploitation Branch:** Uses a simplified single-branch exploitation phase rather than the full two-tier siege attack mechanism described in foundational AVOA literature.

---

## Documentation

Comprehensive guides and technical documentation are organized using the Diátaxis framework:

### Tutorials
* [**Getting Started**](docs/tutorials/getting-started.md) — Step-by-step walkthrough to set up dependencies and run your first emulated SDN-Tor session from scratch.

### How-to Guides
* [**Run the Tor Network**](docs/how-to/run-tor-network.md) — Practical guide to initializing directory authorities, verifying relay handshakes, and testing circuit creation.
* [**Launch the SDN Controller**](docs/how-to/launch-controller.md) — How to configure, boot, and inspect the OSKen application and verify OpenFlow 1.3 socket bindings.
* [**Change Network Topology**](docs/how-to/change-topology.md) — How to configure and change the topology. 
### Explanation
* [**System Architecture**](docs/explanation/architecture.md) — Deep architectural dive into the interaction between the application, control, and infrastructure planes.
* [**Routing Methodology**](docs/explanation/routing-methodology.md) — Theoretical background, mathematical motivation, and comparison of metaheuristics versus machine learning in SDN environments
* [**Tor Integration**](docs/explanation/tor-integration.md)  — How the Tor is configured and works in the project.

---

## Future Work

* **Live Telemetry Ingestion:** Connect the optimization engine to dynamic OpenFlow telemetry metrics (live queue occupancy, port loss, and transit delay counters).
* **Bifurcated Exploitation:** Implement the full two-stage coordinated siege attack logic from Chen et al. (2024).
* **Empirical Benchmarking:** Measure end-to-end circuit latency and packet delivery ratios against baseline OpenFlow shortest-path routing and Equal-Cost Multi-Path (ECMP).
* **Dynamic Failure Recovery:** Automate fast-reroute OpenFlow table failover on switch link-down events.

---

## References

1. **ITor-SDN Framework:**  
   F. A. Yaseen, N. A. Alkhalidi, and H. S. Al-Raweshidy, *"ITor-SDN: Intelligent Tor Networks-Based SDN for Data Forwarding Management,"* IEEE Systems Journal.
2. **AVOA Dynamic Routing Foundation:**  
   Chen, J., Xiao, W., Zhang, H., Zuo, J., & Li, X. (2024). *"Dynamic routing optimization in software-defined networking based on a metaheuristic algorithm."* *Journal of Cloud Computing*, 13. [DOI: 10.1186/s13677-024-00603-1](https://doi.org/10.1186/s13677-024-00603-1).
3. **Original AVOA Formulation:**  
   Abdollahzadeh, B., Gharehchopogh, F. S., & Mirjalili, S. (2021). *"African vultures optimization algorithm: A new nature-inspired metaheuristic technology for global optimization problems."* *Computers & Industrial Engineering*, 158, 107408.

