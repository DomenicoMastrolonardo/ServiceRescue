"""Scarica RE2-OB a revisione fissa e conserva metriche e grafo delle chiamate nominali."""
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

REVISION = 'afeacb11bcc94dadfd1c8f483ee4377b2b8b614e'
BASE = f'https://huggingface.co/datasets/phamquiluan/RCAEval/resolve/{REVISION}/'
ROOT = Path(__file__).resolve().parents[2]
SIGNALS = ['cpu', 'mem', 'socket', 'workload', 'latency-90']


def fetch(name, cache):
    path = cache / name
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        for attempt in range(4):
            try:
                with urllib.request.urlopen(BASE + name, timeout=90) as response:
                    part = path.with_suffix(path.suffix + '.part')
                    with part.open('wb') as output:
                        while block := response.read(1024 * 1024):
                            output.write(block)
                part.replace(path)
                break
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(2 ** attempt)
    return path


def nominal_edges(table, inject_time):
    """Unisce gli span per (traceID, spanID); usa solo span terminati prima del fault."""
    rows = table.to_pylist()
    normal = [r for r in rows if r['startTime'] + r['duration'] < inject_time * 1_000_000]
    lookup = {(r['traceID'], r['spanID']): r['serviceName'] for r in normal}
    counts = {}
    for row in normal:
        parent = lookup.get((row['traceID'], row['parentSpanID']))
        if parent and parent != row['serviceName']:
            key = (parent, row['serviceName'])
            counts[key] = counts.get(key, 0) + 1
    return [{'caller': a, 'callee': b, 'count': n} for (a, b), n in sorted(counts.items())]


def prepare_case(case, cache, destination):
    import pyarrow.parquet as pq
    name = case['case']
    metric_path = fetch(name + '/metrics.parquet', cache)
    trace_path = fetch(name + '/traces.parquet', cache)
    metrics = pq.read_table(metric_path)
    selected = ['time'] + [c for c in metrics.column_names if any(c.endswith('_' + s) for s in SIGNALS)]
    target = destination / (name + '.csv.gz')
    # Un timestamp gzip fisso rende riproducibile il file derivato.
    import io
    with target.open('wb') as stream, gzip.GzipFile(fileobj=stream, mode='wb', mtime=0, filename='') as zipped:
        with io.TextIOWrapper(zipped, encoding='utf-8', newline='') as text:
            writer = csv.DictWriter(text, fieldnames=selected)
            writer.writeheader()
            writer.writerows(metrics.select(selected).to_pylist())
    traces = pq.read_table(trace_path, columns=['traceID', 'spanID', 'parentSpanID', 'serviceName', 'startTime', 'duration'])
    edges = nominal_edges(traces, case['inject_time'])
    result = {**case, 'edges': edges, 'metrics_columns': selected,
              'source_hashes': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in [metric_path, trace_path]},
              'derived_sha256': hashlib.sha256(target.read_bytes()).hexdigest()}
    (destination / (name + '.json')).write_text(json.dumps(result, indent=2) + '\n')
    print(name, 'edges', len(edges), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, default=ROOT / '.cache/rcaeval')
    parser.add_argument('--output', type=Path, default=ROOT / 'data/external/rcaeval')
    args = parser.parse_args()
    import pyarrow.parquet as pq
    args.output.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(Path(__file__).with_name('RCAEval-LICENSE.txt'), args.output / 'LICENSE')
    index = fetch('cases.parquet', args.cache)
    cases = [r for r in pq.read_table(index).to_pylist() if r['dataset'] == 'RE2-OB']
    assert len(cases) == 90
    # Due casi simultanei limitano la memoria occupata dalle tracce.
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda case: prepare_case(case, args.cache, args.output), cases))
    manifest = {'dataset': 'RCAEval RE2-OB', 'revision': REVISION, 'source': BASE,
                'paper': 'https://doi.org/10.1145/3701716.3715290', 'license': 'MIT',
                'cases': [r['case'] for r in results],
                'index_sha256': hashlib.sha256(index.read_bytes()).hexdigest(),
                'signals': SIGNALS, 'topology': 'Per-case calls from spans completed before fault injection; no mandatory-dependency claim.',
                'selection': 'All 90 RE2-OB cases; no selection based on outcomes.'}
    (args.output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
