"""Ricerca a costo uniforme su insiemi di riparazioni con oracolo logico."""
from dataclasses import dataclass
from heapq import heappop, heappush
from itertools import combinations
from time import perf_counter
from .logic import infer
from .domain import simulate_down


@dataclass
class Plan:
    repairs: list
    cost: int
    expanded: int
    seconds: float


def plan(topology, failed, rules, strategy='ucs'):
    if strategy not in ('ucs', 'cheapest'):
        raise ValueError('Strategia sconosciuta')
    failed = frozenset(failed)
    if not failed <= set(topology.nodes):
        raise ValueError('Guasto su nodo sconosciuto')
    if any(topology.costs[s] <= 0 for s in failed):
        raise ValueError('I costi devono essere positivi')
    # La chiusura strutturale reach non serve all'oracolo di ripristino.
    repair_rules = tuple(r for r in rules if r.head[0] in ('down', 'critical_down'))
    started = perf_counter()
    frontier = [(0, ())]
    seen = {()}
    expanded = 0
    while frontier:
        cost, repaired = heappop(frontier)
        expanded += 1
        remaining = failed.difference(repaired)
        if not infer(topology.facts(remaining), repair_rules).query('critical_down'):
            return Plan(list(repaired), cost, expanded, perf_counter() - started)
        candidates = sorted(remaining, key=lambda s: (topology.costs[s], s))
        if strategy == 'cheapest':
            candidates = candidates[:1]
        for s in candidates:
            state = tuple(sorted((*repaired, s)))
            if state not in seen:
                seen.add(state)
                heappush(frontier, (cost + topology.costs[s], state))
    raise RuntimeError('Nessun piano: verificare la KB')


def exhaustive_cost(topology, failed):
    """Oracolo di test: tutti i sottoinsiemi + simulatore indipendente."""
    best = sum(topology.costs[s] for s in failed)
    for size in range(len(failed) + 1):
        for subset in combinations(sorted(failed), size):
            down = simulate_down(topology, set(failed).difference(subset))
            if not down.intersection(topology.critical):
                best = min(best, sum(topology.costs[s] for s in subset))
    return best
