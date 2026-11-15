# Routing Methodology

Understand how the SDN control plane models the Spine-Leaf fabric, generates link metrics via `MiniAVOA`, resolves paths, and installs OpenFlow forwarding rules.

---

## 1. Overview

This document details the routing engine implemented in `super_controller.py`. In this project, path selection across the Spine-Leaf OpenFlow fabric is handled by **MiniAVOA**, a simplified adaptation of the African Vulture Optimization Algorithm (AVOA) integrated with NetworkX and Dijkstra's shortest-path algorithm.

Specifically, this guide covers:
- How the OSKen controller models switches and links as a `NetworkX` graph.
- How `MiniAVOA` generates, bounds, and scores candidate edge-weight vectors.
- The step-by-step execution pipeline from an incoming `PacketIn` event to OpenFlow `FlowMod` rule installation.
- The built-in fallback mechanism and current implementation limitations.

---

## 2. Network Representation

The OSKen controller maintains a logical topology graph $G = (V, E)$ modeled using `NetworkX`:

- **Vertices ($V$):** Represent active Open vSwitch (OVS) datapaths (`s1`–`s7`) discovered via OpenFlow `EventOFPSwitchFeatures` handshakes.
- **Edges ($E$):** Represent bidirectional inter-switch links connecting the Spine layer (`s1`–`s3`) and Leaf layer (`s4`–`s7`).
- **Dimensionality:** The problem dimension (`num_dim`) passed to the optimizer equals the total number of active graph edges $\vert{}E\vert{}$ (12 Spine-Leaf fabric links in the baseline topology).

---

## 3. Edge Weight Generation

Rather than pulling real-time hardware queue counters (`OFPPortStatsReply`), edge weights in the current implementation are synthesized numerically during the optimization search:

1. **Search Boundaries:** Candidate edge weights are constrained to the inclusive range $[1, 20]$ via `np.clip(pop[i], self.lb, self.ub)`.
2. **Vector Representation:** A single candidate solution $\vec{W} = [w_1, w_2, \dots, w_{\vert{}E\vert{}}]$ represents a complete weight assignment across every link in the topology graph.
3. **Graph Mapping:** Once the optimizer resolves the selected vector, each scalar value $w_i$ is written directly to the `'weight'` attribute of edge $(u_i, v_i)$ in the `NetworkX` graph.

---

## 4. African Vulture Optimization Algorithm (AVOA)

`MiniAVOA` adapts the metaheuristic framework proposed by Chen et al. (2024) into a compact solver executed during route resolution. While the `MiniAVOA` class defines default signature parameters of `pop_size=5` and `epochs=2`, the actual SDN workflow invocation executes with **`pop_size=10` and `epochs=5`**.

### 4.1 Candidate Solution Generation
At initialization (`Step 2` of `MiniAVOA_Solve`), the solver constructs a population matrix `pop` of dimensions `(pop_size, num_dim)` (`10 × 12` in the experimental setup). Each row represents an independent candidate weight vector populated with uniform random floating-point values within the inclusive range $[1, 20]$.

During subsequent epochs, candidates update their positions relative to the current global best solution (`best_vulture`) using a randomized probability $P \in [0, 1]$ and an adaptive factor $F$:

$$F = (2r - 1)\left(1 - \frac{t}{T}\right)$$

Where $r$ is a uniform random number in $[0, 1)$, $t$ is the current epoch (`0` through `4`), and $T$ is the total number of epochs (`5`).

- **Exploration Phase ($\lvert F \rvert \ge 1$):**

$$\texttt{pop}[i] = \texttt{best\textunderscore vulture} - \lvert P \cdot \texttt{best\textunderscore vulture} - \texttt{pop}[i] \rvert \cdot F$$

- **Exploitation Phase ($\lvert F \rvert < 1$):**

$$\texttt{pop}[i] = \texttt{best\textunderscore vulture} + (\texttt{best\textunderscore vulture} - \texttt{pop}[i]) \cdot r' \cdot F, \quad r' \in [0, 1)$$

All updated values are clipped via `np.clip(pop[i], self.lb, self.ub)` so that candidate edge weights remain constrained to the inclusive range $[1, 20]$. *(Note: Unlike the full multi-stage AVOA paper, `MiniAVOA` uses a single unified exploitation equation rather than bifurcating into intensive attack and coordinated siege sub-phases.)*

### 4.2 Objective Function
The implementation evaluates candidate weight vectors using a synthetic statistical objective function (`local_fitness_function`):

$$f(W) = \sigma(W) + \mu(W)$$

Where:
- $\sigma(W)$ is the standard deviation of the candidate edge weights.
- $\mu(W)$ is their arithmetic mean.

The fitness function minimizes the mean and standard deviation of the candidate edge-weight vector. Minimizing the mean encourages lower overall edge costs, while minimizing the standard deviation encourages more uniform edge costs. This objective operates on the generated weight vector alone; it does not incorporate live link utilization, congestion, packet loss, or traffic volume.

### 4.3 Solution Evaluation
Every candidate vector in the population is scored by `local_fitness_function` during initialization and after every position update:

1. The solver tracks the lowest scalar fitness score seen so far in `best_fit` and stores the corresponding vector in `best_vulture`.
2. Whenever an updated candidate yields `fit < best_fit`, `best_fit` and `best_vulture` are immediately overwritten.
3. The adaptive factor progressively reduces the magnitude of the position updates across optimization epochs. In the current implementation, the condition for entering the exploration branch ($\lvert F \rvert \ge 1$) is practically never satisfied because the random factor $(2r - 1) \in [-1, 1)$ and epoch-dependent multiplier $(1 - \frac{t}{T})$ normally keep $\lvert F \rvert$ below $1$. Consequently, the implementation predominantly executes the exploitation update equation.

With five executed epochs ($T = 5$, $t \in \{0, 1, 2, 3, 4\}$), the epoch multiplier decreases linearly across iterations without reaching zero:

| Epoch ($t$) | Multiplier $(1 - t/T)$ |
| :---: | :---: |
| `0` | `1.0` |
| `1` | `0.8` |
| `2` | `0.6` |
| `3` | `0.4` |
| `4` | `0.2` |

### 4.4 Route Selection
`MiniAVOA` optimizes the **metric space** (link weights) rather than outputting an explicit sequence of switches directly:

1. Upon completing all 5 epochs, `MiniAVOA_Solve` returns `best_vulture` (the selected weight vector of length $\vert{}E\vert{}$).
2. After the optimizer generates the edge-weight vector, the controller applies these weights to the NetworkX graph (`graph[u][v]['weight'] = weights[i]`).
3. Dijkstra's algorithm then computes the path with the minimum total accumulated edge weight between the source and destination switches.

---

## 5. Dynamic Routing Workflow

When traffic enters the data plane without a matching switch flow rule, the controller executes the end-to-end routing pipeline:

1. **Obtain Network Representation:** Switch `s6` receives a packet from `tor_relay2` (`172.18.0.6`) destined for `tor_cli` (`172.18.0.10`) and forwards an `EventOFPPacketIn` to `super_controller.py`. The controller queries its `NetworkX` graph (`12` Spine-Leaf edges).
2. **Generate Candidate Link Weights:** `AVRO_SDN_Optimizer_Workflow` overrides the class defaults (`pop_size=5, epochs=2`) and invokes `MiniAVOA_Solve(num_dim=12, pop_size=10, epochs=5)`, initializing 10 random 12-dimensional weight vectors bounded in $[1, 20]$.
3. **Evaluate Candidate Solutions:** Over 5 epochs, candidates update predominantly via the exploitation equation, scoring each vector via $f(W) = \sigma(W) + \mu(W)$ and updating `best_vulture`.
4. **Determine Route:** The selected weight vector is applied to the NetworkX graph edges, and Dijkstra's algorithm computes the path with the minimum total accumulated edge weight—for example, `[6, 1, 5]` (`s6 -> s1 -> s5`), logged as:
   ```text
   -- AVRO (Refresh): Routing 172.18.0.6 -> 172.18.0.10 via [6, 1, 5] --
```
    Install Flow Entries: The controller maps switch-to-switch transitions along [6, 1, 5] to physical switch ports and pushes OpenFlow FlowMod rules to s6, s1, and s5.

###  Implementation Pseudocode
```text

// Note: Class signature defaults to pop_size=5, epochs=2;
// the SDN workflow invokes this solver with pop_size=10, epochs=5.
FUNCTION MiniAVOA_Solve(num_dim, fitness_func, pop_size=5, epochs=2):
    // Step 1: Initialize Search Boundaries (Inclusive [1, 20])
    Set lb = 1.0
    Set ub = 20.0

    // Step 2: Initialize Population and Fitness
    Create matrix 'pop' of size (pop_size, num_dim) filled with random values uniformly in [lb, ub]
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
            
            // Calculate adaptive factor (multipliers for T=5: 1.0, 0.8, 0.6, 0.4, 0.2)
            Set P = Random value between 0.0 and 1.0
            Set F = (2 * Random value between 0.0 and 1.0 - 1) * (1 - epoch / epochs)

            // Phase Selection (|F| < 1 normally holds, executing Exploitation)
            IF AbsoluteValue(F) >= 1 THEN
                // Exploration Phase
                pop[i] = best_vulture - AbsoluteValue(P * best_vulture - pop[i]) * F
            ELSE
                // Exploitation Phase: Refine around the current best candidate
                pop[i] = best_vulture + (best_vulture - pop[i]) * (Random value between 0.0 and 1.0) * F
            END IF

            // Boundary Constraints Enforcement: np.clip(pop[i], lb, ub)
            Clip all values in pop[i] to the inclusive range [lb, ub]

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

    // Inline Definition: Synthetic Statistical Objective Function
    FUNCTION local_fitness_function(solution):
        Set standard_deviation = Calculate standard deviation of solution
        Set mean_value = Calculate arithmetic mean of solution
        RETURN standard_deviation + mean_value
    END FUNCTION

    // Step 2: Execute Metaheuristic Search (Explicitly overriding defaults to 10 and 5)
    TRY:
        Set weights = MiniAVOA_Solve(
            num_dim = num_edges, 
            fitness_func = local_fitness_function, 
            pop_size = 10, 
            epochs = 5
        )
    CATCH Exception:
        // Graceful fallback to uniform weight array: [1.0] * self.num_edges
        Print "[AVRO ERROR] Custom AVOA failed"
        Set weights = Array of size num_edges filled with 1.0
    END TRY

    // Step 3: Apply Generated Weights to NetworkX Graph Edges
    FOR i from 0 to minimum of (length of weights, num_edges) - 1:
        Get edge endpoints (u, v) from edges[i]
        Assign graph[u][v]['weight'] = weights[i]
    END FOR

    // Step 4: Minimum-Total-Weight Path Computation via Dijkstra
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

    2. Returns a uniform fallback weight array ([1.0] * self.num_edges).

    3. If optimization fails, the controller falls back to uniform edge weights. Dijkstra can still compute a path using these weights, but this path is not the result of a successful MiniAVOA optimization.

## 8. Limitations

    * Synthetic Weight Generation: Link weights are synthesized statistically during optimization passes rather than derived continuously from live OpenFlow port telemetry (packet loss, queue depth, or measured link delay).

    * Emulated Testbed Constraints: Latency (10ms), bandwidth (10 Mbps), and convergence timings reflect local Containernet/OVS virtualization overhead on a single host rather than distributed physical hardware.

    * Separation of Overlay and Underlay: Tor circuit selection (choosing Guard, Middle, and Exit relays) operates independently at the application layer; MiniAVOA only computes layer-3 switch transit paths between those chosen relays.

    * Anonymity Guarantees: Computing minimum-total-weight underlay transit paths does not inherently strengthen Tor's cryptographic anonymity or defend against end-to-end traffic correlation attacks.

## Related Documents

- [System Architecture](architecture.md)
- [Tor Integration](tor-integration.md)
- [Launch SDN Controller](../how-to/launch-controller.md)
- [Modify Network Topology](../how-to/change-topology.md)

