import numpy as np
import networkx as nx
import random

class MiniAVOA:
    """A custom, lightweight implementation of African Vulture Optimization Algorithm."""
    def __init__(self, num_dim, fitness_func, pop_size=5, epochs=2):
        self.num_dim = num_dim
        self.fitness_func = fitness_func
        self.pop_size = pop_size
        self.epochs = epochs
        self.lb = 1.0
        self.ub = 20.0

    def solve(self):
        # 1. Initialize Population
        pop = np.random.uniform(self.lb, self.ub, (self.pop_size, self.num_dim))
        fitness = np.array([self.fitness_func(ind) for ind in pop])
        
        # 2. Find Best Vulture
        best_idx = np.argmin(fitness)
        best_vulture = pop[best_idx].copy()
        best_fit = fitness[best_idx]

        # 3. Optimization Loop (Search and Attack phases)
        for epoch in range(self.epochs):
            for i in range(self.pop_size):
                # Adaptive factor (simulates hunger/energy)
                P = random.random()
                F = (2 * random.random() - 1) * (1 - epoch/self.epochs)
                
                if abs(F) >= 1:
                    # Exploration Phase: Search for new paths
                    pop[i] = best_vulture - abs(P * best_vulture - pop[i]) * F
                else:
                    # Exploitation Phase: Attack best known path
                    pop[i] = best_vulture + (best_vulture - pop[i]) * random.random() * F

                # Boundary Check
                pop[i] = np.clip(pop[i], self.lb, self.ub)
                
                # Update Fitness
                fit = self.fitness_func(pop[i])
                if fit < best_fit:
                    best_fit = fit
                    best_vulture = pop[i].copy()

        return best_vulture

class AVRO_SDN_Optimizer:
    def __init__(self, graph):
        self.G = graph
        self.edges = list(graph.edges())
        self.num_edges = len(self.edges)

    def fitness_function(self, solution):
        # Objective: Balance link load (low std) and minimize cost (low mean)
        return float(np.std(solution) + np.mean(solution))

    def solve(self):
        try:
            # Use our custom MiniAVOA engine
            optimizer = MiniAVOA(
                num_dim=self.num_edges, 
                fitness_func=self.fitness_function,
                pop_size=10, 
                epochs=5
            )
            solution = optimizer.solve()
            return solution.tolist()
        except Exception as e:
            print(f"[AVRO ERROR] Custom AVOA failed: {e}")
            return [1.0] * self.num_edges

    def get_optimal_path(self, graph, source, destination):
        weights = self.solve()
        for i in range(min(len(weights), self.num_edges)):
            u, v = self.edges[i]
            graph[u][v]['weight'] = float(weights[i])
        
        path = nx.shortest_path(graph, source, destination, weight='weight')
        return path
