## Overview
This project implements a private Tor network integrated with Software Defined Networking (SDN) using the OSKen controller. The objective is to explore how a metaheuristic optimization algorithm can be incorporated into SDN-based routing decisions while maintaining Tor's anonymity properties.
The project was developed as a final-year engineering project.

## Motivation

This project began as a discussion between a group of friends who wanted to experiment with different networking technologies and explore what would happen if they were combined. In particular, we were interested in integrating Tor, which provides anonymous communication, with Software Defined Networking (SDN), which enables centralized and programmable network control.

During our literature review, we came across the paper *"ITor-SDN: Intelligent Tor Networks-Based SDN for Data Forwarding Management"* by F. A. Yaseen, N. A. Alkhalidi, and H. S. Al-Raweshidy. The paper demonstrated how SDN can be integrated with Tor to improve forwarding management through intelligent routing.

While studying this work, we began asking a different question:

> Can adaptive routing be achieved without relying on computationally intensive machine learning techniques?

This led us to investigate metaheuristic optimization algorithms as a lightweight alternative for routing decisions.

Tor is inherently slower than conventional networks because packets are encrypted and decrypted multiple times as they traverse several relays to preserve user anonymity. Since modifying Tor's application-layer protocol was beyond the scope of this project, we instead explored whether routing decisions at the network layer could be improved using SDN and a metaheuristic optimization algorithm.

After reviewing several optimization techniques, we selected the African Vulture Optimization Algorithm (AVOA). Our choice was motivated by the paper *"Dynamic Routing Optimization in Software-Defined Networking Based on a Metaheuristic Algorithm"* by Chen et al. (2024), which reported performance improvements of approximately **16.9%** over deep reinforcement learning approaches and **71.8%** over traditional routing schemes within their experimental environment.

Inspired by these results, we wanted to investigate how AVOA could be integrated into an SDN-controlled private Tor network and evaluate its behavior as an adaptive routing mechanism. Rather than reproducing the existing research exactly, this project explores a different combination of technologies and serves as a proof of concept for integrating a metaheuristic optimization algorithm into an SDN-managed Tor environment.

## Project Objectives

* Build a private Tor network.

* Integrate Tor with an SDN controller.

* Implement routing using the African Vulture Optimization Algorithm.

* Demonstrate adaptive path selection in an SDN environment.


## Architecture

<img width="1788" height="1206" alt="IMG_0811" src="https://github.com/user-attachments/assets/27be3ff8-39b0-49b9-853e-6fd67b0e3961" />


## Technologies Used

* Python

* Containernet

* Open vSwitch

* OSKen

* TOR

* OpenFlow

* Ubuntu


## Routing Methodology

<img width="710" height="284" alt="Screenshot 2026-06-27 at 8 56 21 PM" src="https://github.com/user-attachments/assets/3839fd66-b8fb-418b-b36e-c50b08cdd908" />

>image from *"Chen, Junyan & Xiao, Wei & Zhang, Hongmei & Zuo, Jiacheng & Li, Xinmei. (2024). Dynamic routing optimization in software-defined networking based on a metaheuristic algorithm. Journal of Cloud Computing. 13. 10.1186/s13677-024-00603-1.*"

For the routing algorithm we took direcr inspiration from "Dynamic routing optimization in software-defined networing based on a metaheuristic algorithm" as it allows dynamic network managment and configuration through programming.
 
As you can see in the image above a population of vultures is created who produce a fitness score based on the metrics they bring from traveling in the network. From this data a calculation is made whether to explore more in the network or improve the existing links or choose these weights for the network if they are the best for network performance

    FUNCTION MiniAVOA_Solve(num_dim, fitness_func, pop_size=5, epochs=2):
    // Step 1: Initialize Boundaries
    Set lb = 1.0
    Set ub = 20.0

    // Step 2: Initialize Population and Fitness
    Create matrix 'pop' of size (pop_size, num_dim) filled with random values uniformly between lb and ub
    Create array 'fitness' of size pop_size
    
    FOR each individual 'ind' at index 'k' in pop:
        fitness[k] = fitness_func(ind)
    END FOR

    // Step 3: Identify the initial best vulture
    Find 'best_idx' where fitness is minimized
    Set 'best_vulture' = copy of pop[best_idx]
    Set 'best_fit' = fitness[best_idx]

    // Step 4: Optimization Loop
    FOR epoch from 0 to (epochs - 1):
        FOR i from 0 to (pop_size - 1):
            
            // Calculate adaptive factors
            Set P = Random value between 0.0 and 1.0
            Set F = (2 * Random value between 0.0 and 1.0 - 1) * (1 - epoch / epochs)

            // Phase Selection
            IF AbsoluteValue(F) >= 1 THEN
                // Exploration Phase
                pop[i] = best_vulture - AbsoluteValue(P * best_vulture - pop[i]) * F
            ELSE
                // Exploitation Phase
                pop[i] = best_vulture + (best_vulture - pop[i]) * (Random value between 0.0 and 1.0) * F
            END IF

            // Boundary Constraints Check
            Clip all values in pop[i] so they remain between lb and ub

            // Update fitness and track the global best
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

    // Inline Definition: Fitness Evaluation
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
        // Fallback strategy on execution failure
        Print "[AVRO ERROR] Custom AVOA failed"
        Set weights = Array of size num_edges filled with 1.0
    END TRY

    // Step 3: Apply Optimal Weights to Graph Edges
    FOR i from 0 to minimum of (length of weights, num_edges) - 1:
        Get edge endpoints (u, v) from edges[i]
        Assign graph[u][v]['weight'] = weights[i]
    END FOR

    // Step 4: Route Computation
    Set path = Calculate Dijkstra's shortest path from source to destination using edge 'weight'
    
    RETURN path
    END FUNCTION


| Feature / Step                | Algorithm's logic in research paper                       | Algorithm's logic in project                                    |            
| --------------------------    | -------------------------------------------------------   | ----------------------------------------------------------------|              
|(1) Fitness Dependency         | Calculates fitness using network status S                 | Calculates fitness purely from statisticalproperties (std and mean)of the edge weight array properties (std and mean)of the edge weight array                        |
|(2) Exploitation Granularity   | Splits exploitation (abs(F) < 1) into two sub-phases: intensive attack (abs(F) >= 0.5) nd siege/coordinated attack (abs(F) < 0.5).                | Treats all exploitation under abs(F) < 1 identically with a single branch.           |
|(3) Execution Sequence         | Finds the best vulture at the end of all iterations to compute the final shortest path matrix (Lines 20-22).      | Updates the global best_vulture progressively inside the loop,and updates graph weights iteratively on every lookup.  |

>In this implementation, the AVOA algorithm generates an initial candidate solution vector representing possible routing decisions. The candidate with the lowest objective value is selected, and the SDN controller installs the corresponding forwarding rules. After each iteration, the optimization algorithm updates the candidate solution according to the AVOA search strategy and computes the next routing decision.

## Current Limitations

The current implementation does not use live network telemetry to compute routing decisions. Although the SDN controller manages the network topology and installs forwarding rules, the optimization algorithm currently evolves its candidate solution vectors internally rather than using real-time measurements such as:

* Link utilization
  
* End-to-end latency
  
* Packet loss
  
* Queue occupancy
  
* OpenFlow port statistics

Consequently, the routing process demonstrates the integration of AVOA with the SDN controller rather than a fully closed-loop adaptive routing system note that is a limitation of my implementation rather than inadequecy of the algorithm.

# Future Work

As said above a future addition could add additional complex features from the paper of AVRO to make the system more robust and intelligent like including live network telemetry and a more complex This is a direct API call to the SDN controller's monitoring module. In a real SDN deployment (like Ryu or OpenDaylight), this step actively polls the switches for real-time telemetry metrics, such as:

* Link Utilization / Bandwidth 
  
* Packet Loss Rates
  
* Port Statistics / Queuing Delays

We could also include a Training Iteration Threshold (train): 
>The paper has a training threshold variable. It uses a condition if i < t_train to dynamically decide whether to update parameter F. And have Granular Phase Transitions:

>This project Completely omits train and calculates F using a single, simplified generic formula.

Granular Phase Transitions:
>Within the exploration and exploitation phases, the code checks sub-conditions based on random parameters (e.g., if G1 >= r_G1) to choose between distinct update equations

> This project implements a single, generic placeholder math equation for abs(F) >= 1 and abs(F) < 1.




