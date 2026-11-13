# Routing Methodology

Understand how the SDN control plane models the Spine-Leaf fabric, generates dynamic link metrics via `MiniAVOA`, resolves paths, and installs OpenFlow forwarding rules.

---

## 1. Overview

This document details the routing engine implemented in `super_controller.py`. In this project, path selection across the Spine-Leaf OpenFlow fabric is handled by **MiniAVOA**, a simplified adaptation of the African Vulture Optimization Algorithm (AVOA) integrated with NetworkX and Dijkstra's shortest-path algorithm.

Specifically, this guide covers:
* How the OSKen controller models switches and links as a `NetworkX` graph.
* How `MiniAVOA` generates, bounds, and scores candidate edge-weight vectors.
* The step-by-step execution pipeline from an incoming `PacketIn` event to OpenFlow `FlowMod` rule installation.
* The built-in fallback mechanism and current implementation limitations.

---

## 2. Network Representation

The OSKen controller maintains a logical topology graph $G = (V, E)$ modeled using `NetworkX`:

* **Vertices ($V$):** Represent active Open vSwitch (OVS) datapaths (`s1`–`s7`) discovered via OpenFlow `EventOFPSwitchFeatures` handshakes.
* **Edges ($E$):** Represent bidirectional inter-switch links connecting the Spine layer (`s1`–`s3`) and Leaf layer (`s4`–`s7`).
* **Dimensionality:** The problem dimension (`num_dim`) passed to the optimizer equals the total number of active graph edges $\vert{}E\vert{}$ (12 Spine-Leaf fabric links in the baseline topology).

---

## 3. Edge Weight Generation

Rather than pulling real-time hardware queue counters (`OFPPortStatsReply`), edge weights in the current implementation are synthesized numerically during the optimization search:

1. **Search Boundaries:** Every edge weight is bounded within a continuous floating-point range $[lb, ub] = [1.0, 20.0]$.
2. **Vector Representation:** A single candidate solution $\vec{W} = [w_1, w_2, \dots, w_{\vert{}E\vert{}}]$ represents a complete weight assignment across every link in the topology graph.
3. **Graph Mapping:** Once the optimizer resolves the optimal vector, each scalar value $w_i$ is written directly to the `'weight'` attribute of edge $(u_i, v_i)$ in the `NetworkX` graph.

---

## 4. African Vulture Optimization Algorithm (AVOA)

`MiniAVOA` adapts the metaheuristic framework proposed by Chen et al. (2024) into a compact solver (`pop_size = 10`, `epochs = 5`) executed during route resolution.

### 4.1 Candidate Solution Generation
At initialization (`Step 2` of `MiniAVOA_Solve`), the solver constructs a population matrix `pop` of dimensions `(pop_size, num_dim)`. Each row represents an independent candidate weight vector populated with uniform random floating-point values between `1.0` and `20.0`.

During subsequent epochs, candidates update their positions relative to the current global best solution (`best_vulture`) using a randomized probability $P \in [0, 1]$ and an adaptive decay factor $F$:

$$F = (2 \cdot r - 1) \cdot \left(1 - \frac{\text{epoch}}{\text{epochs}}\right), \quad r \in [0, 1]$$

* **Exploration Phase ($\vert F \vert \ge 1$):** Candidates explore broad, untested weight configurations across the search space:
  $$\text{pop}[i] = \text{best\_vulture} - \vert P \cdot \text{best\_vulture} - \text{pop}[i] \vert \cdot F$$
* **Exploitation Phase ($\vert F \vert < 1$):** Candidates refine weight allocations locally around `best_vulture`:
  $$\text{pop}[i] = \text{best\_vulture} + (\text{best\_vulture} - \text{pop}[i]) \cdot r' \cdot F, \quad r' \in [0, 1]$$

All updated values are clipped to remain strictly within $[1.0, 20.0]$. *(Note: Unlike the full multi-stage AVOA paper, `MiniAVOA` uses a single unified exploitation equation rather than bifurcating into intensive attack and coordinated siege sub-phases.)*

### 4.2 Objective Function
Instead of minimizing raw accumulated path cost directly during the metaheuristic search, `MiniAVOA` evaluates candidate weight vectors using a statistical uniformity objective (`local_fitness_function`):

$$\text{Fitness}(\vec{W}) = \sigma(\vec{W}) + \mu(\vec{W})$$

Where:
* $\sigma(\vec{W})$ is the population standard deviation across all edge weights in the candidate vector.
* $\mu(\vec{W})$ is the arithmetic mean across all edge weights in the candidate vector.

**Optimization Goal:** Minimizing $\sigma(\vec{W}) + \mu(\vec{W})$ penalizes candidate solutions that assign disproportionately high weights to individual links while keeping overall link costs low, encouraging balanced edge weight distributions across the Spine-Leaf fabric.

### 4.3 Solution Evaluation
Every candidate vector in the population is scored by `local_fitness_function` during initialization and after every position update:

1. The solver tracks the lowest scalar fitness score seen so far in `best_fit` and stores the corresponding vector in `best_vulture`.
2. Whenever an updated candidate yields `fit < best_fit`, `best_fit` and `best_vulture` are immediately overwritten.
3. Because the linear damping term $(1 - \frac{\text{epoch}}{\text{epochs}})$ drives $F \to 0$ as epochs progress, the population transitions from global exploration in early iterations to local convergence in final iterations.

### 4.4 Route Selection
`MiniAVOA` optimizes the **metric space** (link weights) rather than outputting an explicit sequence of switches directly:

1. Upon completing all epochs, `MiniAVOA_Solve` returns `best_vulture` (the optimal weight array of length $\vert{}E\vert{}$).
2. `AVRO_SDN_Optimizer_Workflow` iterates through the graph edges and assigns `graph[u][v]['weight'] = weights[i]`.
3. Standard **Dijkstra's shortest path algorithm** executes on the newly weighted `NetworkX` graph between the ingress switch (`source`) and egress switch (`destination`) to produce the final ordered switch path.

---

## 5. Dynamic Routing Workflow

When traffic enters the data plane without a matching switch flow rule, the controller executes the end-to-end routing pipeline:

1. **Obtain Network Representation:** Switch `s6` receives a packet from `tor_relay2` (`172.18.0.6`) destined for `tor_cli` (`172.18.0.10`) and forwards an `EventOFPPacketIn` to `super_controller.py`. The controller queries its `NetworkX` graph (`12` Spine-Leaf edges).
2. **Generate Candidate Link Weights:** `AVRO_SDN_Optimizer_Workflow` invokes `MiniAVOA_Solve(num_dim=12, pop_size=10, epochs=5)`, initializing 10 random 12-dimensional weight vectors bounded in $[1.0, 20.0]$.
3. **Evaluate Candidate Solutions:** Over 5 epochs, candidates shift between exploration and exploitation, scoring each vector via $\sigma(\vec{W}) + \mu(\vec{W})$ and updating `best_vulture`.
4. **Determine Route:** The optimal weight vector is applied to the graph edges, and Dijkstra's algorithm resolves the lowest-weight switch path—for example, `[6, 1, 5]` (`s6 -> s1 -> s5`), logged as:
```text
   -- AVRO (Refresh): Routing 172.18.0.6 -> 172.18.0.10 via [6, 1, 5] --

    Install Flow Entries: The controller maps switch-to-switch transitions along [6, 1, 5] to physical switch ports and pushes OpenFlow FlowMod rules to s6, s1, and s5.

Implementation Pseudocode
Plaintext

FUNCTION MiniAVOA_Solve(num_dim, fitness_func, pop_size=5, epochs=2):
    // Step 1: Initialize Search Boundaries
    Set lb = 1.0
    Set ub = 20.0

    // Step 2: Initialize Population and Fitness
    Create matrix 'pop' of size (pop_size, num_dim) filled with random values uniformly between lb and ub
    Create array 'fitness' of size pop_size

    FOR each individual 'ind' at index 'k' in pop:
        fitness[k] = fitness_func(ind)
    END FOR

    // Step 3: Identify Initial Global Optimum
    Find 'best_idx' where fitness is minimized
    Set 'best_vulture' = copy of pop[best_idx]
    Set 'best_fit' = fitness[best_idx]

    // Step 4: Iterative Optimization Loop
    FOR epoch from 0 to (epochs - 1):
        FOR i from 0 to (pop_size - 1):
            
            // Calculate adaptive exploration/exploitation factor
            Set P = Random value between 0.0 and 1.0
            Set F = (2 * Random value between 0.0 and 1.0 - 1) * (1 - epoch / epochs)

            // Phase Selection
            IF AbsoluteValue(F) >= 1 THEN
                // Exploration Phase: Search broad, untested solution space
                pop[i] = best_vulture - AbsoluteValue(P * best_vulture - pop[i]) * F
            ELSE
                // Exploitation Phase: Refine around the current best candidate
                pop[i] = best_vulture + (best_vulture - pop[i]) * (Random value between 0.0 and 1.0) * F
            END IF

            // Boundary Constraints Enforcement
            Clip all values in pop[i] to ensure they remain within [lb, ub]

            // Evaluate fitness and update global best candidate
            Set fit = fitness_func(pop[i])
            IF fit < best_fit THEN
                best_fit = fit
                best_vulture = copy of pop[i]
            END IF

        END FOR
    END FOR

    RETURN best_vulture
END FUNCTION

FUNCTION AVRO_SDN_Optimizer_Workflow(graph, source, destination):
    // Step 1: Analyze Network Topology
    Extract 'edges' list from graph
    Set num_edges = length of edges

    // Inline Definition: Statistical Objective Function
    FUNCTION local_fitness_function(solution):
        Set standard_deviation = Calculate population standard deviation of solution
        Set mean_value = Calculate population mean of solution
        RETURN standard_deviation + mean_value
    END FUNCTION

    // Step 2: Execute Metaheuristic Search
    TRY:
        Set weights = MiniAVOA_Solve(
            num_dim = num_edges, 
            fitness_func = local_fitness_function, 
            pop_size = 10, 
            epochs = 5
        )
    CATCH Exception:
        // Graceful fallback to uniform weight distribution on runtime failure
        Print "[AVRO ERROR] Custom AVOA failed"
        Set weights = Array of size num_edges filled with 1.0
    END TRY

    // Step 3: Apply Optimal Weights to Graph Edges
    FOR i from 0 to minimum of (length of weights, num_edges) - 1:
        Get edge endpoints (u, v) from edges[i]
        Assign graph[u][v]['weight'] = weights[i]
    END FOR

    // Step 4: Route Computation via Dijkstra Shortest Path
    Set path = Calculate Dijkstra's shortest path from source to destination using edge 'weight'

    RETURN path
END FUNCTION
```
## 6. OpenFlow Flow Installation

Once Dijkstra returns the ordered switch path (e.g., [6, 1, 5]), the controller enforces the path across the data plane:

    1. Port Resolution: For each adjacent switch pair (u,v) in the path, the controller looks up the egress port on switch u connected to switch v, plus the final host-facing egress port on the destination leaf switch.

    2. Match Criteria: Constructs an OpenFlow 1.3 match header specifying Layer-3 source and destination IP addresses (ipv4_src, ipv4_dst) or MAC addresses.

    3. Action Set: Defines an OFPActionOutput instruction directing matching packets out of the resolved egress port.

    4. Rule Deployment: Sends an OFPFlowMod message to every switch along the path so subsequent packets in the same flow are switched directly in OVS without triggering PacketIn controller interrupts.

## 7. Fallback Routing Mechanism

To ensure network resilience if the metaheuristic optimizer encounters an exception (such as a graph dimension mismatch or numerical failure), AVRO_SDN_Optimizer_Workflow wraps MiniAVOA_Solve in a TRY / CATCH block:

    1. Logs [AVRO ERROR] Custom AVOA failed to the controller console.

    2. Generates a fallback weight array of size num_edges filled uniformly with 1.0.

    3. Applies the uniform weights to the graph and executes standard hop-count Dijkstra shortest path routing, preventing packet blackholing.

## 8. Limitations

    * Synthetic Weight Generation: Link weights are synthesized statistically during optimization passes rather than derived continuously from live OpenFlow port telemetry (packet loss, queue depth, or measured link delay).

    * Emulated Testbed Constraints: Latency (10ms), bandwidth (10 Mbps), and convergence timings reflect local Containernet/OVS virtualization overhead on a single host rather than distributed physical hardware.

    * Separation of Overlay and Underlay: Tor circuit selection (choosing Guard, Middle, and Exit relays) operates independently at the application layer; MiniAVOA only optimizes layer-3 switch transit paths between those chosen relays.

    * Anonymity Guarantees: Optimizing underlay transit paths improves load distribution and latency characteristics,but does not inherently strengthen Tor's cryptographic anonymity or defend against end-to-end traffic correlation attacks.

    * Baseline Benchmarking Required: Quantitative performance gains (throughput, jitter, and flow setup latency) must be empirically benchmarked against standard baseline protocols such as OSPF or static shortest-path Dijkstra under identical traffic loads.

## Related Documents

- [System Architecture](architecture.md)
- [Tor Integration](tor-integration.md)
- [Launch SDN Controller](../hot-to/launch-controller.md)
- [Modify Network Topology](../how-to/change-topology.md)

