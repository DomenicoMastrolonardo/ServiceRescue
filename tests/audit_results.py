"""Audit degli artefatti salvati: python tests/audit_results.py results/full."""
import csv
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
from sklearn.metrics import f1_score, balanced_accuracy_score, average_precision_score, brier_score_loss


def read_csv(path):
    with path.open(encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def audit(output):
    output = Path(output)
    project = Path(__file__).resolve().parents[1]
    run = json.loads((output / 'run.json').read_text())
    assert run['status'] == 'complete'
    assert hashlib.sha256((output / 'dataset.csv').read_bytes()).hexdigest() == run['dataset_sha256']
    for filename, expected in run['sha256'].items():
        assert hashlib.sha256((project / filename).read_bytes()).hexdigest() == expected, filename
    dataset = read_csv(output / 'dataset.csv')
    groups = {int(r['sample_id']): int(r['group']) for r in dataset}
    targets = {int(r['sample_id']): int(r['target']) for r in dataset}
    splits = json.loads((output / 'splits.json').read_text())
    test_ids = {}
    for repeat in range(run['repeats']):
        seen = []
        for split in [s for s in splits if s['repeat'] == repeat]:
            train, test = set(split['train_ids']), set(split['test_ids'])
            assert train.isdisjoint(test) and train | test == set(groups)
            assert {groups[i] for i in train}.isdisjoint({groups[i] for i in test})
            seen.extend(test)
            test_ids[(repeat, split['fold'])] = test
            inner_seen = []
            for inner in split['inner']:
                a, b = set(inner['train_ids']), set(inner['validation_ids'])
                assert a | b == train and a.isdisjoint(b)
                assert {groups[i] for i in a}.isdisjoint({groups[i] for i in b})
                inner_seen.extend(b)
            assert sorted(inner_seen) == sorted(train)
        assert sorted(seen) == sorted(groups)
    predictions = read_csv(output / 'predictions.csv')
    folds = read_csv(output / 'cv_folds.csv')
    comparisons = len(run['models']) * len(run['feature_sets']) + len(run['baselines'])
    assert len(folds) == run['outer'] * run['repeats'] * comparisons
    assert len(predictions) == len(dataset) * run['repeats'] * comparisons
    for fold in folds:
        selected = [p for p in predictions if all(p[k] == fold[k] for k in ['model', 'feature_set', 'repeat', 'fold'])]
        ids = [int(p['sample_id']) for p in selected]
        assert len(ids) == len(set(ids))
        assert set(ids) == test_ids[(int(fold['repeat']), int(fold['fold']))]
        y = np.array([targets[i] for i in ids])
        assert all(int(p['target']) == targets[int(p['sample_id'])] for p in selected)
        pred = np.array([int(p['prediction']) for p in selected])
        prob = np.array([float(p['probability']) for p in selected])
        assert np.all(np.isfinite(prob)) and np.all((prob >= 0) & (prob <= 1))
        recalculated = {'f1_macro': f1_score(y, pred, average='macro', zero_division=0),
                        'balanced_accuracy': balanced_accuracy_score(y, pred),
                        'average_precision': average_precision_score(y, prob),
                        'brier': brier_score_loss(y, prob)}
        for metric, value in recalculated.items():
            assert np.isclose(value, float(fold[metric])), (metric, fold)
    for row in read_csv(output / 'cv_summary.csv'):
        selected = [f for f in folds if (f['model'], f['feature_set']) == (row['model'], row['feature_set'])]
        for metric in ['f1_macro', 'balanced_accuracy', 'average_precision', 'brier']:
            values = np.array([float(f[metric]) for f in selected])
            assert np.isclose(values.mean(), float(row[metric + '_mean']))
            assert np.isclose(values.std(ddof=1), float(row[metric + '_std']))
    print(f"AUDIT OK: {len(dataset)} osservazioni, {len(splits)} split esterni, "
          f"{len(folds)} valutazioni, {len(predictions)} predizioni; hash, gruppi e metriche coerenti.")
    bayes_predictions = read_csv(output / 'bayesian_predictions.csv')
    bayes_folds = read_csv(output / 'bayesian_folds.csv')
    networks = json.loads((output / 'bayesian_networks.json').read_text())
    assert len(bayes_folds) == len(splits) == len(networks)
    assert len(bayes_predictions) == len(dataset) * run['repeats']
    for fold, network in zip(bayes_folds, networks):
        selected = [r for r in bayes_predictions if (r['repeat'], r['fold']) == (fold['repeat'], fold['fold'])]
        ids = [int(r['sample_id']) for r in selected]
        assert len(ids) == len(set(ids)) and set(ids) == test_ids[(int(fold['repeat']), int(fold['fold']))]
        y = [targets[i] for i in ids]
        pred = [int(r['prediction']) for r in selected]
        proba = [float(r['probability']) for r in selected]
        assert np.isclose(f1_score(y, pred, average='macro'), float(fold['f1_macro']))
        assert np.isclose(brier_score_loss(y, proba), float(fold['brier']))
        split = next(s for s in splits if (s['repeat'], s['fold']) == (network['repeat'], network['fold']))
        features = network['nodes'][1:]
        train_values = [[float(dataset[i][f]) for f in features] for i in split['train_ids']]
        assert np.allclose(np.median(train_values, axis=0), network['thresholds'])
        for cpd in network['cpds']:
            assert np.allclose(np.array(cpd).sum(axis=-1), 1)
    print(f"BAYES OK: {len(bayes_folds)} fold, {len(bayes_predictions)} predizioni, soglie di training e CPD normalizzate.")
    audit_monitoring(output, run)


def audit_monitoring(output, run):
    # Ricostruisce allarmi da centroidi salvati e ricontrolla gli effetti con l'oracolo.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
    from servicerescue.domain import Topology, simulate_down
    from servicerescue.unsupervised import FEATURES, METHODS, distances
    for name, expected in run['monitoring']['sha256'].items():
        assert hashlib.sha256((output / name).read_bytes()).hexdigest() == expected, name
    nominal, observed = (read_csv(output / f'monitoring_{name}.csv') for name in ['nominal', 'observed'])
    truth = json.loads((output / 'monitoring_truth.json').read_text())
    topologies = [Topology(**{k: v for k, v in row.items() if k != 'group'})
                  for row in json.loads((output / 'topologies.json').read_text())]
    models = json.loads((output / 'monitoring_models.json').read_text())
    predictions = read_csv(output / 'monitoring_predictions.csv')
    folds = read_csv(output / 'monitoring_folds.csv')
    groups = np.array([int(r['group']) for r in nominal])
    ids = np.array([int(r['sample_id']) for r in nominal])
    X = np.array([[float(r[c]) for c in FEATURES] for r in nominal])
    Z = np.array([[float(r[c]) for c in FEATURES] for r in observed])
    assert len(predictions) == len(truth) * run['repeats'] * len(METHODS)
    assert len(models) == run['outer'] * run['repeats']
    for repeat in range(run['repeats']):
        assert sorted(g for m in models if m['repeat'] == repeat for g in m['test_groups']) == sorted(set(groups))
    for model in models:
        fit, cal, test = (set(model[k]) for k in ['fit_groups', 'calibration_groups', 'test_groups'])
        assert not (fit & cal or fit & test or cal & test)
        assert fit | cal | test == set(groups)
        np.testing.assert_allclose(model['mean'], X[np.isin(groups, list(fit))].mean(axis=0))
        np.testing.assert_allclose(model['scale'], X[np.isin(groups, list(fit))].std(axis=0))
        calibration = (X[np.isin(groups, list(cal))] - model['mean']) / model['scale']
        test_idx = np.flatnonzero(np.isin(groups, list(test)))
        for method in METHODS:
            if method == 'FixedThreshold':
                alarm = (Z[test_idx, 1] >= .60) | (Z[test_idx, 0] >= .85)
            else:
                centers = np.array(model['centers' if method == 'KMeans' else 'single_center'])
                assert np.isclose(np.quantile(distances(calibration, centers), .95), model['thresholds'][method])
                alarm = distances((Z[test_idx] - model['mean']) / model['scale'], centers) > model['thresholds'][method]
            selected = [p for p in predictions if p['method'] == method and
                        int(p['repeat']) == model['repeat'] and int(p['fold']) == model['fold']]
            assert sorted(int(p['sample_id']) for p in selected) == sorted(set(ids[test_idx]))
            for p in selected:
                sid = int(p['sample_id'])
                expected = {observed[test_idx[j]]['node'] for j in np.flatnonzero(ids[test_idx] == sid) if alarm[j]}
                assert set(json.loads(p['alarms'])) == expected
                topology = topologies[truth[sid]['group']]
                assert int(p['target']) == truth[sid]['critical_down']
                assert int(p['prediction']) == int(bool(simulate_down(topology, expected).intersection(topology.critical)))
            row = next(f for f in folds if f['method'] == method and int(f['repeat']) == model['repeat'] and int(f['fold']) == model['fold'])
            local_truth = [observed[i]['node'] in truth[ids[i]]['failed'] for i in test_idx]
            actual = {'local_f1': f1_score(local_truth, alarm, zero_division=0),
                      'local_false_alarm_rate': alarm[~np.array(local_truth)].mean(),
                      'critical_f1_macro': f1_score([int(p['target']) for p in selected], [int(p['prediction']) for p in selected], average='macro'),
                      'critical_balanced_accuracy': balanced_accuracy_score([int(p['target']) for p in selected], [int(p['prediction']) for p in selected])}
            for metric, value in actual.items():
                assert np.isclose(value, float(row[metric]))
    for row in read_csv(output / 'monitoring_summary.csv'):
        for metric in ['local_f1', 'local_false_alarm_rate', 'critical_f1_macro', 'critical_balanced_accuracy']:
            values = [float(f[metric]) for f in folds if f['method'] == row['method']]
            assert np.isclose(np.mean(values), float(row[metric + '_mean']))
            assert np.isclose(np.std(values, ddof=1), float(row[metric + '_std']))
    print(f"MONITORING OK: {len(models)} split, {len(predictions)} predizioni; calibrazione, allarmi e conseguenze verificati.")


if __name__ == '__main__':
    audit(sys.argv[1] if len(sys.argv) > 1 else 'results/full')
