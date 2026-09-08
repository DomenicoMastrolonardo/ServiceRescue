import argparse
from dataclasses import asdict
import json
from pathlib import Path
from .domain import SCENARIOS, demo_topology
from .logic import ROOT, infer, load_rules
from .planning import plan


def main():
    parser = argparse.ArgumentParser(description='ServiceRescue-KB — progetto ICon')
    sub = parser.add_subparsers(dest='command', required=True)
    demo = sub.add_parser('demo', help='Spiegazione logica e ripristino di un piccolo caso')
    demo.add_argument('--output', type=Path, default=ROOT / 'results/demo.json')
    experiment = sub.add_parser('experiment', help='Dataset, CV annidata e benchmark di ricerca')
    experiment.add_argument('--profile', choices=['smoke', 'full'], default='full')
    experiment.add_argument('--seed', type=int, default=42)
    experiment.add_argument('--scenario', choices=list(SCENARIOS), default='standard')
    experiment.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.command == 'demo':
        topology = demo_topology()
        failed = {'power', 'db_b'}
        rules = load_rules()
        closure = infer(topology.facts(failed), rules)
        result = {'scenario': topology.to_dict(), 'confirmed_failures': sorted(failed),
                  'down': closure.query('down'),
                  'explanation': closure.explain(('critical_down', 'portal')),
                  'optimal_plan': asdict(plan(topology, failed, rules)),
                  'cheapest_plan': asdict(plan(topology, failed, rules, 'cheapest'))}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        rendered = json.dumps(result, indent=2, ensure_ascii=False)
        args.output.write_text(rendered + '\n', encoding='utf-8')
        print(rendered)
    else:
        from .experiments import run
        default_name = args.profile if args.scenario == 'standard' else f'{args.profile}_{args.scenario}'
        run(args.profile, args.seed, args.output or ROOT / 'results' / default_name, args.scenario)
