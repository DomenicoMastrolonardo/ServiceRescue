"""Valuta il monitoraggio su RE2-OB con partizioni temporali e parametri prefissati."""
import argparse
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import sys

import numpy as np
import sklearn
from sklearn.cluster import KMeans
from sklearn.metrics import balanced_accuracy_score, f1_score, silhouette_score
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from servicerescue.logic import infer, load_rules

METHODS = ('SingleCenter', 'KMeans', 'MaxDeviation')
METRICS = ('f1_macro', 'balanced_accuracy', 'false_alarm_rate', 'fault_period_recall')
CONFIG = {'seed': 42, 'fit_fraction': .6, 'calibration_fraction': .2,
          'quantile': .95, 'ks': list(range(2, 8)), 'n_init': 10,
          'silhouette_sample': 400}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def write_csv(path, rows):
    with Path(path).open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def load_case(folder, name):
    metadata = json.loads((folder / (name + '.json')).read_text())
    path = folder / (name + '.csv.gz')
    if sha(path) != metadata['derived_sha256']:
        raise ValueError(f'Hash diverso per {name}')
    with gzip.open(path, 'rt', newline='') as stream:
        reader = csv.DictReader(stream)
        columns = [c for c in reader.fieldnames if c != 'time']
        rows = list(reader)
    times = np.array([float(r['time']) for r in rows])
    X = np.array([[float(r[c]) if r[c] else np.nan for c in columns] for r in rows])
    X[~np.isfinite(X)] = np.nan
    if not np.all(np.isfinite(times)) or not np.all(np.diff(times) > 0):
        raise ValueError('Timestamp non finiti, duplicati o non ordinati')
    return metadata, columns, times, X


def temporal_split(times, injection):
    normal = np.flatnonzero(times < injection)
    faults = np.flatnonzero(times >= injection)
    if len(normal) < 50 or not len(faults):
        raise ValueError('Storico nominale o periodo di guasto insufficiente')
    fit_end = int(len(normal) * CONFIG['fit_fraction'])
    cal_end = fit_end + int(len(normal) * CONFIG['calibration_fraction'])
    return normal[:fit_end], normal[fit_end:cal_end], np.r_[normal[cal_end:], faults]


def preprocess_fit(X):
    keep = np.flatnonzero(np.isfinite(X).any(axis=0))
    if not len(keep):
        raise ValueError('Nessuna feature osservata nel training')
    medians = np.nanmedian(X[:, keep], axis=0)
    filled = np.where(np.isfinite(X[:, keep]), X[:, keep], medians)
    scaler = StandardScaler().fit(filled)
    return {'keep': keep.tolist(), 'medians': medians.tolist(),
            'mean': scaler.mean_.tolist(), 'scale': scaler.scale_.tolist()}


def transform(X, state):
    selected = X[:, state['keep']]
    filled = np.where(np.isfinite(selected), selected, state['medians'])
    return (filled - state['mean']) / state['scale']


def distance(X, centers):
    return np.sqrt(((X[:, None, :] - np.asarray(centers)[None, :, :]) ** 2).sum(axis=2).min(axis=1))


def scores(X, state, method):
    if method == 'MaxDeviation':
        return np.abs(X).max(axis=1)
    return distance(X, state['centers'] if method == 'KMeans' else state['single_center'])


def fit_model(reference, calibration):
    state = preprocess_fit(reference)
    X, C = transform(reference, state), transform(calibration, state)
    state['single_center'] = X.mean(axis=0, keepdims=True).tolist()
    sample_ids = np.random.default_rng(CONFIG['seed']).choice(
        len(X), min(CONFIG['silhouette_sample'], len(X)), replace=False)
    sample = X[sample_ids]
    candidates = []
    with threadpool_limits(limits=1):
        unique = len(np.unique(X, axis=0))
        for k in CONFIG['ks']:
            if k >= len(X) or k > unique:
                continue
            km = KMeans(n_clusters=k, n_init=CONFIG['n_init'], random_state=CONFIG['seed']).fit(X)
            labels = km.predict(sample)
            score = silhouette_score(sample, labels) if 1 < len(np.unique(labels)) < len(sample) else -1.
            candidates.append((k, float(score), km.cluster_centers_.tolist()))
    state['silhouettes'] = [{'k': k, 'score': s} for k, s, _ in candidates]
    if candidates:
        state['k'], _, state['centers'] = max(candidates, key=lambda v: (v[1], -v[0]))
    else:
        state['k'], state['centers'] = 1, state['single_center']
    state['thresholds'] = {m: float(np.quantile(scores(C, state, m), CONFIG['quantile'])) for m in METHODS}
    return state


def metrics(target, prediction):
    return {'f1_macro': float(f1_score(target, prediction, average='macro', zero_division=0)),
            'balanced_accuracy': float(balanced_accuracy_score(target, prediction)),
            'false_alarm_rate': float(np.mean(prediction[target == 0])),
            'fault_period_recall': float(np.mean(prediction[target == 1]))}


def graph_example(meta, columns, state, X, times, test, rules):
    Z = transform(X[test], state)
    alarms = scores(Z, state, 'KMeans') > state['thresholds']['KMeans']
    found = np.flatnonzero(alarms)
    if not len(found):
        return {'case': meta['case'], 'detected': False}
    row = int(found[0])
    feature = columns[state['keep'][int(np.argmax(np.abs(Z[row])))]]
    service = feature.rsplit('_', 1)[0]
    # Solo un alias esplicito fra nomi delle metriche e nomi delle tracce.
    service = {'frontend': 'frontendservice'}.get(service, service)
    facts = [('calls', e['caller'], e['callee']) for e in meta['edges']]
    facts.append(('sensor_alarm', service))
    closure = infer(facts, rules)
    affected = closure.query('possibly_affected')
    return {'case': meta['case'], 'detected': True, 'time': float(times[test[row]]),
            'largest_deviation_metric': feature, 'sensor_alarm': service,
            'possibly_affected': [a[0] for a in affected],
            'proofs': [closure.explain(('possibly_affected', a[0])) for a in affected]}


def summarize(rows):
    result = []
    for fault in ['ALL', *sorted({r['fault'] for r in rows})]:
        for method in METHODS:
            selected = [r for r in rows if r['method'] == method and (fault == 'ALL' or r['fault'] == fault)]
            item = {'fault': fault, 'method': method, 'cases': len(selected)}
            for metric in METRICS:
                values = np.array([float(r[metric]) for r in selected])
                item[metric + '_mean'] = float(values.mean())
                item[metric + '_std'] = float(values.std(ddof=1))
            result.append(item)
    return result


def evaluate(folder, output):
    manifest = json.loads((folder / 'manifest.json').read_text())
    names = manifest['cases']
    if len(names) != 90 or len(set(names)) != 90:
        raise ValueError('Attesi tutti i 90 casi RE2-OB')
    output.mkdir(parents=True, exist_ok=True)
    run = {'status': 'running', 'dataset': manifest['dataset'], 'config': CONFIG,
           'protocol': 'Per-case adaptation: first 60% normal fit, next 20% calibration, remainder normal and all post-injection test.',
           'target': 'time >= injection; exposure to injected fault, not verified service outage',
           'versions': {'numpy': np.__version__, 'sklearn': sklearn.__version__},
           'input_hashes': {p.name: sha(p) for p in sorted(folder.iterdir()) if p.is_file()},
           'code_hashes': {str(p.relative_to(ROOT)): sha(p) for p in [Path(__file__), ROOT / 'src/servicerescue/logic.py', ROOT / 'kb/observed_calls.json']}}
    write_json(output / 'run.json', run)
    models, rows, examples = [], [], []
    rules = load_rules(ROOT / 'kb/observed_calls.json')
    predictions_count = 0
    with (output / 'predictions.csv.gz').open('wb') as raw:
        with gzip.GzipFile(fileobj=raw, mode='wb', filename='', mtime=0) as zipped:
            with io.TextIOWrapper(zipped, encoding='utf-8', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=['case', 'method', 'row', 'time', 'target', 'score', 'prediction'])
                writer.writeheader()
                for number, name in enumerate(names):
                    meta, columns, times, X = load_case(folder, name)
                    fit, cal, test = temporal_split(times, meta['inject_time'])
                    state = fit_model(X[fit], X[cal])
                    state.update({'case': name, 'columns': columns, 'fit_rows': fit.tolist(),
                                  'calibration_rows': cal.tolist(), 'test_rows': test.tolist()})
                    models.append(state)
                    Z = transform(X[test], state)
                    target = (times[test] >= meta['inject_time']).astype(int)
                    for method in METHODS:
                        values = scores(Z, state, method)
                        pred = (values > state['thresholds'][method]).astype(int)
                        rows.append({'case': name, 'fault': meta['fault'], 'method': method,
                                     'test_normal': int((target == 0).sum()), 'test_fault': int(target.sum()),
                                     **metrics(target, pred)})
                        for i, index in enumerate(test):
                            writer.writerow({'case': name, 'method': method, 'row': int(index), 'time': times[index],
                                             'target': int(target[i]), 'score': values[i], 'prediction': int(pred[i])})
                        predictions_count += len(test)
                    examples.append(graph_example(meta, columns, state, X, times, test, rules))
                    if (number + 1) % 15 == 0:
                        print(f'RCAEval: {number + 1}/90 casi valutati', flush=True)
    write_json(output / 'models.json', models)
    write_json(output / 'graph_examples.json', examples)
    write_csv(output / 'cases.csv', rows)
    summary = summarize(rows)
    write_csv(output / 'summary.csv', summary)
    run.update({'status': 'complete', 'cases': len(names), 'predictions': predictions_count,
                'result_hashes': {name: sha(output / name) for name in
                                 ['models.json', 'graph_examples.json', 'cases.csv', 'summary.csv', 'predictions.csv.gz']}})
    write_json(output / 'run.json', run)
    print(json.dumps([r for r in summary if r['fault'] == 'ALL'], indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, default=ROOT / 'data/external/rcaeval')
    parser.add_argument('--output', type=Path, default=ROOT / 'results/external/rcaeval')
    args = parser.parse_args()
    evaluate(args.data, args.output)
