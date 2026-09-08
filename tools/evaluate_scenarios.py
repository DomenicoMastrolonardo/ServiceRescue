"""Valuta tre dataset sintetici predefiniti e aggrega soltanto run auditati.

Uso: python tools/evaluate_scenarios.py [--summarize-only]
Le famiglie appartengono allo stesso dominio: non sono tre domini reali.
"""
import argparse
import csv
import json
from pathlib import Path
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'tests'))
from servicerescue.domain import SCENARIOS
from servicerescue.experiments import write_csv, write_json
from audit_results import audit

# Fissati prima dei nuovi run: nessuna ricerca del seed migliore.
RUNS = [('standard', 42, 'full'), ('redundant', 73, 'full_redundant'), ('dense', 101, 'full_dense')]


def read(path):
    with path.open(newline='', encoding='utf-8') as stream:
        return list(csv.DictReader(stream))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--summarize-only', action='store_true')
    args = parser.parse_args()
    destination = ROOT / 'results/scenarios'
    destination.mkdir(parents=True, exist_ok=True)
    protocol = {
        'status': 'running', 'domain': 'synthetic service dependencies',
        'purpose': 'Sensitivity to redundancy and graph size/density; no cross-domain validation.',
        'protocol': 'Separate nested grouped CV for each dataset, 5 outer x 2 repeats x 3 inner.',
        'runs': [{'scenario': name, 'seed': seed, 'directory': directory, **SCENARIOS[name]}
                 for name, seed, directory in RUNS],
    }
    write_json(destination / 'protocol.json', protocol)
    combined = {name: [] for name in ['cv_summary', 'ablation_deltas', 'bayesian_summary', 'monitoring_summary']}
    datasets, reasoning = [], []
    for name, seed, directory in RUNS:
        output = ROOT / 'results' / directory
        if not args.summarize_only:
            subprocess.run([sys.executable, str(ROOT / 'main.py'), 'experiment', '--profile', 'full',
                            '--scenario', name, '--seed', str(seed), '--output', str(output)], check=True, cwd=ROOT)
        audit(output)
        run = json.loads((output / 'run.json').read_text())
        assert run['scenario'] == name and run['seed'] == seed and run['profile'] == 'full'
        assert run['scenario_parameters'] == SCENARIOS[name]
        datasets.append({'scenario': name, 'seed': seed, 'groups': run['groups'], 'samples': run['samples'],
                         'prevalence': run['prevalence'], **SCENARIOS[name],
                         'dataset_sha256': run['dataset_sha256']})
        for filename, values in combined.items():
            values.extend({'scenario': name, **row} for row in read(output / (filename + '.csv')))
        cases = read(output / 'reasoning_cases.csv')
        stats = {'scenario': name, 'snapshots': len(cases),
                 'prolog_agreement': run['prolog']['all_predicates_agreement']}
        for field in ['input_facts', 'closure_facts', 'rounds', 'matches', 'seconds']:
            values = [float(row[field]) for row in cases]
            stats[field + '_mean'] = statistics.mean(values)
            stats[field + '_std'] = statistics.stdev(values)
        reasoning.append(stats)
    assert len({row['dataset_sha256'] for row in datasets}) == len(RUNS)
    write_csv(destination / 'datasets.csv', datasets)
    write_csv(destination / 'reasoning_summary.csv', reasoning)
    for name, values in combined.items():
        write_csv(destination / (name + '.csv'), values)
    protocol['status'] = 'complete'
    protocol['samples_total'] = sum(row['samples'] for row in datasets)
    write_json(destination / 'protocol.json', protocol)
    print(f'Tre dataset verificati; tabelle aggregate: {destination}', flush=True)


if __name__ == '__main__':
    main()
