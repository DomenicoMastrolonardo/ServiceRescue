"""Regimi nominali K-Means -> anomalie locali -> conseguenze nella KB.

Non raggruppa il dataset etichettato di previsione. Fit e calibrazione leggono
solo sensori nominali; i guasti iniettati sono un oracolo di valutazione separato.
"""
import hashlib
import json
from pathlib import Path
import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score, f1_score, balanced_accuracy_score
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits
from .domain import Topology, simulate_down
from .logic import infer, load_rules

FEATURES = ['cpu', 'errors', 'latency']
METHODS = ['FixedThreshold', 'SingleCenter', 'KMeans']


def distances(X, centers):
    return np.sqrt(((X[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2).min(axis=1))


class RegimeDetector:
    def __init__(self, seed=42, ks=range(2, 8), quantile=.95):
        self.seed, self.ks, self.quantile = seed, list(ks), quantile

    def fit(self, reference, calibration):
        reference, calibration = np.asarray(reference, float), np.asarray(calibration, float)
        if reference.ndim != 2 or calibration.ndim != 2 or reference.shape[1] != 3 or calibration.shape[1] != 3:
            raise ValueError('Attese tre colonne: cpu, errors, latency')
        if len(reference) < max(self.ks) + 1 or not len(calibration):
            raise ValueError('Riferimento o calibrazione insufficienti')
        if not np.isfinite(reference).all() or not np.isfinite(calibration).all():
            raise ValueError('Sensori non finiti')
        self.scaler_ = StandardScaler().fit(reference)
        X = self.scaler_.transform(reference)
        rng = np.random.default_rng(self.seed)
        fit_rows = rng.choice(len(X), min(2000, len(X)), replace=False)
        sample = X[fit_rows[:min(400, len(fit_rows))]]
        self.scores_, candidates = [], []
        with threadpool_limits(limits=1):
            for k in self.ks:
                km = KMeans(n_clusters=k, n_init=10, random_state=self.seed).fit(X[fit_rows])
                labels = km.predict(sample)
                score = silhouette_score(sample, labels) if 1 < len(np.unique(labels)) < len(sample) else -1.
                self.scores_.append({'k': k, 'silhouette': float(score)})
                candidates.append(km.cluster_centers_)
        best = int(np.argmax([row['silhouette'] for row in self.scores_]))
        self.centers_ = candidates[best]
        self.k_ = self.ks[best]
        # La baseline usa lo stesso sottoinsieme e la stessa calibrazione.
        self.single_ = X[fit_rows].mean(axis=0, keepdims=True)
        cal = self.scaler_.transform(calibration)
        self.thresholds_ = {
            'KMeans': float(np.quantile(distances(cal, self.centers_), self.quantile)),
            'SingleCenter': float(np.quantile(distances(cal, self.single_), self.quantile))}
        return self

    def predict(self, observations, method='KMeans'):
        raw = np.asarray(observations, float)
        if method == 'FixedThreshold':
            return (raw[:, 1] >= .60) | (raw[:, 0] >= .85)
        if method not in self.thresholds_:
            raise ValueError('Metodo sconosciuto')
        centers = self.centers_ if method == 'KMeans' else self.single_
        return distances(self.scaler_.transform(raw), centers) > self.thresholds_[method]

    def state(self):
        return {'k': self.k_, 'mean': self.scaler_.mean_.tolist(), 'scale': self.scaler_.scale_.tolist(),
                'centers': self.centers_.tolist(), 'single_center': self.single_.tolist(),
                'thresholds': self.thresholds_, 'quantile': self.quantile}


def monitoring_data(topologies, snapshots, seed):
    nominal_rng, fault_rng = np.random.default_rng(seed + 700), np.random.default_rng(seed + 701)
    nominal, observed, truth = [], [], []
    for group, topology in enumerate(topologies):
        for snapshot in range(snapshots):
            sample_id = group * snapshots + snapshot
            # Due modi nominali non annotati: carico leggero e carico elevato.
            high = nominal_rng.random() < .45
            mean = [.72, .08, 110.] if high else [.25, .03, 45.]
            clean = nominal_rng.normal(mean, [.045, .012, 8.], (len(topology.nodes), 3))
            clean[:, :2] = np.clip(clean[:, :2], 0, 1)
            clean[:, 2] = np.maximum(clean[:, 2], 1)
            local_failed = fault_rng.random(len(clean)) < .08
            changed = clean.copy()
            changed[local_failed] += [.16, .20, 90.]
            changed[:, :2] = np.clip(changed[:, :2], 0, 1)
            for node, reference, measurement in zip(topology.nodes, clean, changed):
                key = {'sample_id': sample_id, 'group': group, 'node': node}
                nominal.append({**key, **dict(zip(FEATURES, map(float, reference)))})
                observed.append({**key, **dict(zip(FEATURES, map(float, measurement)))})
            failed = [node for node, active in zip(topology.nodes, local_failed) if active]
            truth.append({'sample_id': sample_id, 'group': group, 'failed': failed,
                          'critical_down': int(bool(simulate_down(topology, failed).intersection(topology.critical)))})
    return nominal, observed, truth


def monitoring_splits(groups, outer, repeats, seed):
    all_groups = np.unique(groups)
    for repeat in range(repeats):
        shuffled = np.random.default_rng(seed + 710 + repeat).permutation(all_groups)
        for fold, test in enumerate(np.array_split(shuffled, outer)):
            train = shuffled[~np.isin(shuffled, test)]
            n_cal = max(1, int(np.ceil(.2 * len(train))))
            calibration, fit = train[:n_cal], train[n_cal:]
            if not len(fit) or not len(test):
                raise ValueError('Infrastrutture insufficienti per gli split')
            yield {'repeat': repeat, 'fold': fold, 'fit_groups': fit.tolist(),
                   'calibration_groups': calibration.tolist(), 'test_groups': test.tolist()}


def evaluate(output, config, seed):
    from .experiments import write_csv, write_json
    output = Path(output)
    raw_topologies = json.loads((output / 'topologies.json').read_text())
    topologies = [Topology(**{k: v for k, v in row.items() if k != 'group'}) for row in raw_topologies]
    nominal, observed, truth = monitoring_data(topologies, config['snapshots'], seed)
    write_csv(output / 'monitoring_nominal.csv', nominal)
    write_csv(output / 'monitoring_observed.csv', observed)
    write_json(output / 'monitoring_truth.json', truth)
    X = np.array([[r[c] for c in FEATURES] for r in nominal])
    measurements = np.array([[r[c] for c in FEATURES] for r in observed])
    groups = np.array([r['group'] for r in nominal])
    ids = np.array([r['sample_id'] for r in nominal])
    rules = tuple(r for r in load_rules() if r.head[0] in ['down', 'critical_down'])
    folds, predictions, models, silhouettes, profiles = [], [], [], [], []
    for split in monitoring_splits(groups, config['outer'], config['repeats'], seed):
        key = {k: split[k] for k in ['repeat', 'fold']}
        fit = np.isin(groups, split['fit_groups'])
        calibration = np.isin(groups, split['calibration_groups'])
        test = np.flatnonzero(np.isin(groups, split['test_groups']))
        detector = RegimeDetector(seed + split['repeat'] * 10 + split['fold']).fit(X[fit], X[calibration])
        models.append({**split, **detector.state()})
        silhouettes.extend({**key, **row} for row in detector.scores_)
        centers = detector.scaler_.inverse_transform(detector.centers_)
        profiles.extend({**key, 'cluster': c, **dict(zip(FEATURES, map(float, center)))}
                        for c, center in enumerate(centers))
        for method in METHODS:
            alarms = detector.predict(measurements[test], method)
            local_truth = np.array([observed[i]['node'] in truth[ids[i]]['failed'] for i in test])
            truth_root, pred_root = [], []
            for sid in np.unique(ids[test]):
                positions = np.flatnonzero(ids[test] == sid)
                failed = [observed[test[j]]['node'] for j in positions if alarms[j]]
                topology = topologies[truth[sid]['group']]
                closure = infer(topology.facts(failed), rules)
                prediction = int(bool(closure.query('critical_down')))
                expected = int(bool(simulate_down(topology, failed).intersection(topology.critical)))
                if prediction != expected:
                    raise AssertionError('Anomalie e propagazione KB incoerenti')
                truth_root.append(truth[sid]['critical_down'])
                pred_root.append(prediction)
                predictions.append({**key, 'method': method, 'sample_id': int(sid),
                                    'alarms': json.dumps(failed), 'prediction': prediction,
                                    'target': truth[sid]['critical_down']})
            if len(np.unique(truth_root)) != 2:
                raise ValueError('Test di monitoraggio con una sola classe: aumentare i gruppi')
            folds.append({**key, 'method': method, 'k': detector.k_ if method == 'KMeans' else 1,
                          'local_f1': float(f1_score(local_truth, alarms, zero_division=0)),
                          'local_false_alarm_rate': float(alarms[~local_truth].mean()),
                          'critical_f1_macro': float(f1_score(truth_root, pred_root, average='macro', zero_division=0)),
                          'critical_balanced_accuracy': float(balanced_accuracy_score(truth_root, pred_root))})
    summary = []
    for method in METHODS:
        row = {'method': method, 'n_folds': config['outer'] * config['repeats']}
        for metric in ['local_f1', 'local_false_alarm_rate', 'critical_f1_macro', 'critical_balanced_accuracy']:
            values = [f[metric] for f in folds if f['method'] == method]
            row[metric + '_mean'], row[metric + '_std'] = float(np.mean(values)), float(np.std(values, ddof=1))
        summary.append(row)
    write_json(output / 'monitoring_models.json', models)
    for name, values in [('monitoring_folds', folds), ('monitoring_predictions', predictions),
                         ('monitoring_summary', summary), ('silhouette_folds', silhouettes), ('cluster_profiles', profiles)]:
        write_csv(output / (name + '.csv'), values)
    scores = []
    for k in range(2, 8):
        values = [r['silhouette'] for r in silhouettes if r['k'] == k]
        scores.append({'k': k, 'silhouette_mean': float(np.mean(values)), 'silhouette_std': float(np.std(values, ddof=1))})
    write_csv(output / 'silhouette_summary.csv', scores)
    return {'snapshots': len(truth), 'node_observations': len(observed), 'n_folds': len(models),
            'sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in sorted(output.glob('monitoring_*')) if p.is_file()},
            'features': FEATURES, 'methods': METHODS, 'summary': summary}


def plot_silhouette(output, destination):
    from .analysis import read_rows
    import matplotlib.pyplot as plt
    scores = read_rows(Path(output) / 'silhouette_summary.csv')
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.errorbar([int(r['k']) for r in scores], [float(r['silhouette_mean']) for r in scores],
                yerr=[float(r['silhouette_std']) for r in scores], marker='o', capsize=4)
    ax.set(xlabel='k', ylabel='Silhouette: media ± dev. standard',
           title='Regimi nominali: selezione sul solo training')
    fig.tight_layout()
    fig.savefig(Path(destination) / '01_silhouette_scores.png', dpi=160)
    plt.close(fig)
