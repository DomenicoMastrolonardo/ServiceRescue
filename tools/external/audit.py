"""Ricostruisce preprocessing, soglie e predizioni della valutazione RCAEval salvata."""
import argparse
from collections import defaultdict
import csv
import gzip
import json
from pathlib import Path

import numpy as np
from evaluate import ROOT, METHODS, METRICS, CONFIG, load_case, temporal_split, preprocess_fit, transform, scores, metrics, sha, summarize


def read_csv(path):
    with Path(path).open(newline='', encoding='utf-8') as stream:
        return list(csv.DictReader(stream))


def audit(folder, output):
    run = json.loads((output / 'run.json').read_text())
    assert run['status'] == 'complete' and run['cases'] == 90 and run['config'] == CONFIG
    for key, base in [('input_hashes', folder), ('result_hashes', output), ('code_hashes', ROOT)]:
        for name, digest in run[key].items():
            assert sha(base / name) == digest, name
    models = json.loads((output / 'models.json').read_text())
    manifest = json.loads((folder / 'manifest.json').read_text())
    assert [m['case'] for m in models] == manifest['cases']
    with gzip.open(output / 'predictions.csv.gz', 'rt') as stream:
        predictions = list(csv.DictReader(stream))
    assert len(predictions) == run['predictions']
    indexed = defaultdict(list)
    for row in predictions:
        indexed[(row['case'], row['method'])].append(row)
    assert len(indexed) == 90 * len(METHODS)
    case_rows = {(r['case'], r['method']): r for r in read_csv(output / 'cases.csv')}
    assert len(case_rows) == 90 * len(METHODS)
    for model in models:
        meta, columns, times, X = load_case(folder, model['case'])
        fit, cal, test = temporal_split(times, meta['inject_time'])
        assert columns == model['columns']
        for expected, key in [(fit, 'fit_rows'), (cal, 'calibration_rows'), (test, 'test_rows')]:
            assert expected.tolist() == model[key]
        assert set(fit).isdisjoint(cal) and set(fit).isdisjoint(test) and set(cal).isdisjoint(test)
        assert sorted([*fit, *cal, *test]) == list(range(len(times)))
        assert times[fit[-1]] < times[cal[0]] < times[test[0]]
        state = preprocess_fit(X[fit])
        for key in ['keep', 'medians', 'mean', 'scale']:
            np.testing.assert_allclose(state[key], model[key])
        Z = transform(X[test], model)
        nominal = transform(X[cal], model)
        np.testing.assert_allclose(transform(X[fit], model).mean(axis=0), model['single_center'][0])
        if model['silhouettes']:
            best = max(model['silhouettes'], key=lambda s: (s['score'], -s['k']))
            assert model['k'] == best['k']
        target = (times[test] >= meta['inject_time']).astype(int)
        for method in METHODS:
            threshold = np.quantile(scores(nominal, model, method), CONFIG['quantile'])
            np.testing.assert_allclose(threshold, model['thresholds'][method])
            value = scores(Z, model, method)
            predicted = (value > threshold).astype(int)
            saved = indexed[(model['case'], method)]
            assert [int(r['row']) for r in saved] == test.tolist()
            np.testing.assert_allclose([float(r['time']) for r in saved], times[test])
            np.testing.assert_allclose([float(r['score']) for r in saved], value)
            np.testing.assert_array_equal([int(r['prediction']) for r in saved], predicted)
            np.testing.assert_array_equal([int(r['target']) for r in saved], target)
            recorded = case_rows[(model['case'], method)]
            assert recorded['fault'] == meta['fault']
            assert int(recorded['test_normal']) == int((target == 0).sum())
            assert int(recorded['test_fault']) == int(target.sum())
            for key, val in metrics(target, predicted).items():
                np.testing.assert_allclose(float(recorded[key]), val)
    expected = summarize(list(case_rows.values()))
    saved = read_csv(output / 'summary.csv')
    assert len(saved) == len(expected)
    for a, b in zip(saved, expected):
        assert (a['fault'], a['method'], int(a['cases'])) == (b['fault'], b['method'], b['cases'])
        for key in METRICS:
            for suffix in ['_mean', '_std']:
                np.testing.assert_allclose(float(a[key + suffix]), b[key + suffix])
    examples = json.loads((output / 'graph_examples.json').read_text())
    assert [e['case'] for e in examples] == manifest['cases']
    for example in examples:
        if not example['detected']:
            continue
        meta = json.loads((folder / (example['case'] + '.json')).read_text())
        # Verifica procedurale indipendente dei possibili chiamanti a monte.
        edges = [(e['caller'], e['callee']) for e in meta['edges']]
        reached, frontier = set(), {example['sensor_alarm']}
        while frontier:
            parents = {a for a, b in edges if b in frontier} - reached
            reached |= parents
            frontier = parents
        assert sorted(reached) == sorted(example['possibly_affected'])
        assert all(p['fact'][0] == 'possibly_affected' for p in example['proofs'])
    print(f'RCAEval AUDIT OK: 90 casi, {len(predictions)} predizioni, hash, split temporali, soglie, metriche e grafi.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, default=ROOT / 'data/external/rcaeval')
    parser.add_argument('--output', type=Path, default=ROOT / 'results/external/rcaeval')
    args = parser.parse_args()
    audit(args.data, args.output)
