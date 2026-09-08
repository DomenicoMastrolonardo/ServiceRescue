"""Infrastrutture, simulatore indipendente e generazione degli esempi.

Il futuro stocastico non chiama il motore logico e non legge feature derivate.
"""
from dataclasses import dataclass, asdict
import numpy as np


@dataclass
class Topology:
    nodes: list
    requires: list
    replicas: list
    critical: list
    costs: dict
    zones: dict

    def facts(self, failures=()):
        return ([('requires', *r) for r in self.requires]
                + [('replicas', *r) for r in self.replicas]
                + [('critical', s) for s in self.critical]
                + [('alarm', s) for s in sorted(failures)])

    def to_dict(self):
        return asdict(self)


SCENARIOS = {
    'standard': dict(min_nodes=10, max_nodes=18, replica_probability=.45, extra_dependency_probability=.35),
    'redundant': dict(min_nodes=10, max_nodes=18, replica_probability=.80, extra_dependency_probability=.15),
    'dense': dict(min_nodes=20, max_nodes=30, replica_probability=.15, extra_dependency_probability=.75),
}


def make_topology(rng, n=14, replica_probability=.45, extra_dependency_probability=.35):
    if n < 3 or not 0 <= replica_probability <= 1 or not 0 <= extra_dependency_probability <= 1:
        raise ValueError('Dimensione o probabilità topologiche non valide')
    nodes = [f"n{i:02d}" for i in range(n)]
    requires, replicas = [], []
    for i in range(3, n):
        # Tutti gli archi puntano verso indici inferiori: DAG nel generatore.
        parents = rng.choice(i, size=2, replace=False)
        if rng.random() < replica_probability:
            replicas.append([nodes[i], nodes[int(parents[0])], nodes[int(parents[1])]])
        else:
            requires.append([nodes[i], nodes[int(parents[0])]])
            if rng.random() < extra_dependency_probability:
                requires.append([nodes[i], nodes[int(parents[1])]])
    return Topology(nodes, requires, replicas, [nodes[-1]],
                    {s: int(rng.integers(1, 10)) for s in nodes},
                    {s: int(rng.integers(0, 3)) for s in nodes})


def simulate_down(topology, failed):
    """Oracolo procedurale distinto dal Datalog, valido anche con cicli."""
    down = set(failed)
    while True:
        before = set(down)
        for service, dependency in topology.requires:
            if dependency in down:
                down.add(service)
        for service, a, b in topology.replicas:
            if a in down and b in down:
                down.add(service)
        if before == down:
            return down


def sample_observation(rng, topology):
    stress = rng.uniform(0, .32)
    severity = np.clip(rng.beta(1.3, 4.5, len(topology.nodes)) + stress, 0, 1)
    errors = np.clip(severity + rng.normal(0, .09, len(severity)), 0, 1)
    cpu = np.clip(.2 + .72 * severity + rng.normal(0, .09, len(severity)), 0, 1)
    latency = np.clip(25 + 180 * severity + rng.normal(0, 12, len(severity)), 1, None)
    return {s: {"errors": float(errors[i]), "cpu": float(cpu[i]),
                "latency": float(latency[i])} for i, s in enumerate(topology.nodes)}, severity


def observed_alarms(observation):
    # Soglie di scenario fissate prima della valutazione, non apprese su y.
    return {s for s, v in observation.items() if v['errors'] >= .60 or v['cpu'] >= .85}


def sample_future(rng, topology, severity):
    shocks = rng.random(3) < .025
    probabilities = .015 + .60 * severity ** 2
    failed = {s for i, s in enumerate(topology.nodes)
              if rng.random() < probabilities[i] or shocks[topology.zones[s]]}
    down = simulate_down(topology, failed)
    return int(bool(down.intersection(topology.critical)))


def demo_topology():
    return Topology(
        ['power', 'db_a', 'db_b', 'api', 'portal'],
        [['db_a', 'power'], ['api', 'db_a'], ['portal', 'api']],
        [['portal', 'db_a', 'db_b']], ['portal'],
        {'power': 4, 'db_a': 7, 'db_b': 2, 'api': 5, 'portal': 9},
        {'power': 0, 'db_a': 0, 'db_b': 1, 'api': 1, 'portal': 2})
