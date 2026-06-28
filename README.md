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

>The figure illustrates the general workflow of the original AVOA algorithm. The implementation in this repository is a simplified adaptation whose differences are summarized below.

For the routing algorithm we took direct inspiration from "Dynamic routing optimization in software-defined networing based on a metaheuristic algorithm" as it allows dynamic network managment and configuration through programming.
 
As you can see in the image above a population of vultures is created who produce a fitness score based on the metrics they bring from traveling in the network. From this data a calculation is made whether to explore more in the network or improve the existing links or choose these weights for the network if they are the best for network performance


Overview
This code defines an automated routing system that optimizes network performance. It uses a custom AI engine inspired by vulture behaviors (MiniAVOA) to find the best configuration of edge weights in a network graph, which it then uses to route data traffic smoothly along the shortest available path.

The Two Main Steps
1. The AI Optimization Engine (MiniAVOA)
  * Goal: Find an ideal set of line metrics (weights) that balances the entire network.
  * How it works: It creates a small group ("population") of random network weight combinations. It loops through a series of refinement rounds ("epochs").
  * The Strategy: In each round, it uses an adaptive formula to decide whether to search wild, untested areas of the network (Exploration Phase) or narrow down and refine the best known configuration (Exploitation Phase). It continuously keeps track of the absolute best configuration it finds.


2. The Routing Process (AVRO SDN Optimizer)
   * Goal: Map out the final traffic path from a starting point (source) to an ending point (destination).
   * How it works:
     1. It analyzes the network topology to count all available links.
     2. It passes this data to the AI engine, defining a "good setup" as one where edge weights are low on average and evenly balanced (minimizing variance).
     3. Once the AI returns the optimized weights, it injects them back into the network map.
     4. Finally, it calculates a classic shortest-path route (Dijkstra's algorithm) based on those custom weights and outputs the optimal path.

for more understanding of the algorithm in the project check out https://github.com/Aditya-Ghag-24/Sdn_tor_avro/blob/main/routing_docs.md


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

* Integrate live OpenFlow telemetry.

* Replace the statistical fitness function with real network measurements.

* Implement the complete training threshold mechanism described by *" Dynamic routing optimization in software-defined networking based         on a metaheuristic algorithm.*"

* Implement granular exploration and exploitation phases.

* Evaluate performance under larger network topologies.

* Compare against shortest-path routing and ECMP.







