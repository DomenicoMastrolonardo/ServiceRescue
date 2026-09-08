"""Regimi nominali e anomalie per la KB; K-Means con scelta di k via silhouette."""
import argparse
import json
from servicerescue.logic import ROOT
from servicerescue.unsupervised import evaluate

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', choices=['full', 'full_redundant', 'full_dense'], default='full')
    args = parser.parse_args()
    source = ROOT / 'results' / args.run
    config = json.loads((source / 'run.json').read_text())
    output = ROOT / 'results' / ('unsupervised_' + args.run)
    output.mkdir(parents=True, exist_ok=True)
    (output / 'topologies.json').write_bytes((source / 'topologies.json').read_bytes())
    result = evaluate(output, config, config['seed'])
    print(f"Monitoraggio: {result['n_folds']} fold; risultati in {output}")
