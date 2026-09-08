"""SWI-Prolog reale via subprocess, senza dipendenza dal ponte pyswip."""
import json
from pathlib import Path
import re
import shutil
import subprocess
from time import perf_counter
from .domain import Topology, observed_alarms
from .features import extract
from .logic import ROOT, Closure, infer

DERIVED = {'edge', 'reach', 'down', 'critical_down', 'exposed', 'degraded'}


def write_facts(cases, path):
    with Path(path).open('w', encoding='utf-8') as f:
        f.write(':- discontiguous snapshot/1, requires/3, replicas/4, alarm/2, critical/2.\n')
        for sample_id, facts in cases:
            f.write(f'snapshot({int(sample_id)}).\n')
            for predicate, *args in facts:
                if predicate not in {'requires', 'replicas', 'alarm', 'critical'}:
                    raise ValueError('Predicato di ingresso non supportato')
                if any(not re.fullmatch(r'[a-z][a-zA-Z0-9_]*', a) for a in args):
                    raise ValueError('Identificatore Prolog non valido')
                f.write(f"{predicate}({int(sample_id)},{','.join(args)}).\n")


def query_batch(cases, directory):
    executable = shutil.which('swipl')
    if executable is None:
        raise RuntimeError('SWI-Prolog non trovato: installare swi-prolog-nox (Linux) o SWI-Prolog (Windows/macOS).')
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    facts = directory / 'facts.pl'
    write_facts(cases, facts)
    started = perf_counter()
    result = subprocess.run([executable, '-q', '-s', str(ROOT / 'kb/kb.pl'),
                             '-g', 'main', '--', str(facts.resolve())],
                            text=True, capture_output=True, check=True, timeout=120)
    (directory / 'prolog_closure.jsonl').write_text(result.stdout, encoding='utf-8')
    rows = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
    mapping = {int(r['sample_id']): set(map(tuple, r['facts'])) for r in rows}
    if len(mapping) != len(rows) or set(mapping) != {int(i) for i, _ in cases}:
        raise AssertionError('Output Prolog incompleto o duplicato')
    version = subprocess.run([executable, '--version'], text=True, capture_output=True, check=True).stdout.strip()
    return mapping, {'engine': version, 'seconds': perf_counter() - started, 'snapshots': len(rows)}


def materialize(output, rules):
    from .experiments import write_csv, write_json
    output = Path(output)
    topology_rows = json.loads((output / 'topologies.json').read_text())
    topologies = {r['group']: Topology(**{k: v for k, v in r.items() if k != 'group'}) for r in topology_rows}
    observations = [json.loads(line) for line in (output / 'observations.jsonl').read_text().splitlines()]
    cases = [(r['sample_id'], topologies[r['group']].facts(observed_alarms(r['observation']))) for r in observations]
    closures, metadata = query_batch(cases, output)
    rows = []
    for observation, (_, facts) in zip(observations, cases):
        sample_id, group = observation['sample_id'], observation['group']
        expected = {f for f in infer(facts, rules).facts if f[0] in DERIVED}
        if closures[sample_id] != expected:
            raise AssertionError(f'SWI-Prolog e Datalog divergono sullo snapshot {sample_id}')
        closure = Closure(set(map(tuple, facts)) | closures[sample_id], {}, 0, 0, 0.)
        values, _ = extract(topologies[group], observation['observation'], rules, closure=closure)
        rows.append({'sample_id': sample_id, 'group': group,
                     'snapshot': sum(r['group'] == group for r in observations[:sample_id]),
                     **values, 'target': observation['target']})
    metadata['all_predicates_agreement'] = len(rows)
    write_csv(output / 'dataset.csv', rows)
    write_json(output / 'prolog_run.json', metadata)
    return rows, metadata
