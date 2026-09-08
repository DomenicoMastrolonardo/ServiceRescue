"""Feature prive di etichette: nessun fit globale o accesso al futuro."""
import numpy as np
from .domain import observed_alarms
from .logic import infer

BASE = ['root_cpu', 'root_errors', 'root_latency', 'n_nodes', 'n_requires', 'n_replicas']
LOCAL = ['mean_cpu', 'max_cpu', 'mean_errors', 'max_errors', 'alarm_fraction']
KB = ['root_down', 'down_fraction', 'reachable_fraction', 'exposed_fraction',
      'reachable_down_fraction', 'degraded_fraction']
FEATURE_SETS = {'BASE': BASE, 'BASE+LOCAL': BASE + LOCAL, 'BASE+KB': BASE + LOCAL + KB}


def extract(topology, observation, rules, closure=None):
    alarms = observed_alarms(observation)
    closure = infer(topology.facts(alarms), rules) if closure is None else closure
    root = topology.critical[0]
    n = len(topology.nodes)
    reachable = {d for s, d in closure.query('reach') if s == root}
    down = {s for s, in closure.query('down')}
    values = {
        'root_cpu': observation[root]['cpu'], 'root_errors': observation[root]['errors'],
        'root_latency': observation[root]['latency'], 'n_nodes': n,
        'n_requires': len(topology.requires), 'n_replicas': len(topology.replicas),
        'alarm_fraction': len(alarms) / n, 'root_down': int(root in down),
        'down_fraction': len(down) / n, 'reachable_fraction': len(reachable) / n,
        'exposed_fraction': len(reachable & alarms) / max(1, len(reachable)),
        'reachable_down_fraction': len(reachable & down) / max(1, len(reachable)),
        'degraded_fraction': len(closure.query('degraded')) / n,
    }
    for sensor in ['cpu', 'errors']:
        data = [v[sensor] for v in observation.values()]
        values[f'mean_{sensor}'] = float(np.mean(data))
        values[f'max_{sensor}'] = float(np.max(data))
    return values, closure
