"""Generazione dei dati e materializzazione tramite SWI-Prolog."""
import argparse
from servicerescue.experiments import PROFILES, build_dataset
from servicerescue.logic import ROOT, load_rules
from servicerescue.prolog import materialize

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=PROFILES, default='full')
    args = parser.parse_args()
    output = ROOT / 'results' / args.profile
    output.mkdir(parents=True, exist_ok=True)
    rules = load_rules()
    build_dataset(PROFILES[args.profile], 42, output, rules)
    _, metadata = materialize(output, rules)
    print(metadata)
