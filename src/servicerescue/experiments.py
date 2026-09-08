"""Nested CV a gruppi, ablation, verifica del ragionamento e della ricerca."""
import csv
from dataclasses import asdict
import hashlib
import json
import platform
from pathlib import Path
from time import perf_counter
import numpy as np
import scipy
import sklearn
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (f1_score, balanced_accuracy_score,
                             average_precision_score, brier_score_loss)
from sklearn.model_selection import GridSearchCV, StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits
from .domain import (SCENARIOS, make_topology, sample_observation, sample_future,
                     observed_alarms, simulate_down)
from .features import FEATURE_SETS, extract
from .logic import ROOT, load_rules
from .planning import plan, exhaustive_cost

METRICS = ['f1_macro', 'balanced_accuracy', 'average_precision', 'brier']
PROFILES = {
    'smoke': dict(groups=18, snapshots=4, outer=3, inner=2, repeats=1, planning_cases=6),
    'full': dict(groups=120, snapshots=8, outer=5, inner=3, repeats=2, planning_cases=60),
}


def write_csv(path, rows):
    if not rows:
        raise ValueError('Nessun risultato da salvare')
    with Path(path).open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')


def build_dataset(config, seed, output, rules):
    # Stream distinti: cambiare il campionamento del futuro non cambia X.
    structure_rng = np.random.default_rng(seed)
    observation_rng = np.random.default_rng(seed + 1)
    outcome_rng = np.random.default_rng(seed + 2)
    rows, topologies, stats = [], [], []
    scenario = SCENARIOS[config.get('scenario', 'standard')]
    with (output / 'observations.jsonl').open('w', encoding='utf-8') as raw:
        for group in range(config['groups']):
            topology = make_topology(
                structure_rng, int(structure_rng.integers(scenario['min_nodes'], scenario['max_nodes'] + 1)),
                scenario['replica_probability'], scenario['extra_dependency_probability'])
            topologies.append({'group': group, **topology.to_dict()})
            for snapshot in range(config['snapshots']):
                observation, severity = sample_observation(observation_rng, topology)
                features, closure = extract(topology, observation, rules)
                target = sample_future(outcome_rng, topology, severity)
                row = {'sample_id': len(rows), 'group': group, 'snapshot': snapshot,
                       **features, 'target': target}
                rows.append(row)
                raw.write(json.dumps({'sample_id': row['sample_id'], 'group': group,
                                      'observation': observation, 'target': target}) + '\n')
                expected = simulate_down(topology, observed_alarms(observation))
                actual = {s for s, in closure.query('down')}
                if expected != actual:
                    raise AssertionError('Datalog e simulatore divergono')
                stats.append({'sample_id': row['sample_id'], 'n_nodes': len(topology.nodes),
                              'input_facts': len(topology.facts(observed_alarms(observation))),
                              'closure_facts': len(closure.facts), 'rounds': closure.rounds,
                              'matches': closure.matches, 'seconds': closure.seconds,
                              'derived_down': len(actual), 'oracle_agreement': 1})
    write_json(output / 'topologies.json', topologies)
    write_csv(output / 'dataset.csv', rows)
    write_csv(output / 'reasoning_cases.csv', stats)
    return rows, stats


def model_configs(seed):
    return {
        'LogisticRegression': (
            Pipeline([('scale', StandardScaler()),
                      ('clf', LogisticRegression(max_iter=2000, random_state=seed))]),
            {'clf__C': [.1, 1., 10.], 'clf__class_weight': [None, 'balanced']}),
        'RandomForest': (
            Pipeline([('clf', RandomForestClassifier(n_estimators=60, random_state=seed, n_jobs=1))]),
            {'clf__max_depth': [4, None], 'clf__min_samples_leaf': [3, 10]}),
        'GradientBoosting': (
            Pipeline([('clf', GradientBoostingClassifier(n_estimators=60, random_state=seed))]),
            {'clf__max_depth': [1, 2], 'clf__learning_rate': [.05, .1]}),
    }


def metrics(y, prediction, probability):
    return {'f1_macro': float(f1_score(y, prediction, average='macro', zero_division=0)),
            'balanced_accuracy': float(balanced_accuracy_score(y, prediction)),
            'average_precision': float(average_precision_score(y, probability)),
            'brier': float(brier_score_loss(y, probability))}


def group_splits(y, groups, count, seed):
    cv = StratifiedGroupKFold(n_splits=count, shuffle=True, random_state=seed)
    splits = list(cv.split(np.zeros((len(y), 1)), y, groups))
    for train, test in splits:
        if set(groups[train]) & set(groups[test]):
            raise AssertionError('Contaminazione tra gruppi')
        if len(np.unique(y[train])) < 2 or len(np.unique(y[test])) < 2:
            raise ValueError('Fold con una sola classe: aumentare la dimensione del dataset')
    return splits


def evaluate_ml(rows, config, seed, output):
    y = np.array([r['target'] for r in rows])
    groups = np.array([r['group'] for r in rows])
    matrices = {name: np.array([[r[c] for c in cols] for r in rows], dtype=float)
                for name, cols in FEATURE_SETS.items()}
    folds, predictions, manifest = [], [], []
    for repeat in range(config['repeats']):
        outer = group_splits(y, groups, config['outer'], seed + 100 + repeat)
        for fold, (train, test) in enumerate(outer):
            inner = group_splits(y[train], groups[train], config['inner'], seed + 200 + repeat * 10 + fold)
            manifest.append({'repeat': repeat, 'fold': fold,
                             'train_ids': train.tolist(), 'test_ids': test.tolist(),
                             'inner': [{'train_ids': train[a].tolist(), 'validation_ids': train[b].tolist()}
                                       for a, b in inner]})
            configs = model_configs(seed + repeat * 10 + fold)
            print(f"CV ripetizione {repeat+1}/{config['repeats']}, fold {fold+1}/{config['outer']}", flush=True)
            for feature_set, X in matrices.items():
                for name, (estimator, grid) in configs.items():
                    search = GridSearchCV(estimator, grid, scoring='f1_macro', cv=inner,
                                          n_jobs=1, error_score='raise', refit=True)
                    started = perf_counter()
                    search.fit(X[train], y[train])
                    probability = search.predict_proba(X[test])[:, 1]
                    prediction = search.predict(X[test])
                    folds.append({'repeat': repeat, 'fold': fold, 'model': name,
                                  'feature_set': feature_set, 'n_test': len(test),
                                  **metrics(y[test], prediction, probability),
                                  'fit_seconds': perf_counter() - started,
                                  'best_params': json.dumps(search.best_params_, sort_keys=True)})
                    predictions.extend({'repeat': repeat, 'fold': fold, 'sample_id': int(i),
                                        'model': name, 'feature_set': feature_set, 'target': int(y[i]),
                                        'prediction': int(prediction[j]), 'probability': float(probability[j])}
                                       for j, i in enumerate(test))
            for name in ['DummyPrior', 'LogicOnly']:
                if name == 'DummyPrior':
                    dummy = DummyClassifier(strategy='prior').fit(matrices['BASE'][train], y[train])
                    prob = dummy.predict_proba(matrices['BASE'][test])[:, 1]
                    pred = dummy.predict(matrices['BASE'][test])
                else:
                    pred = np.array([rows[i]['root_down'] for i in test])
                    prob = pred.astype(float)
                folds.append({'repeat': repeat, 'fold': fold, 'model': name,
                              'feature_set': '-', 'n_test': len(test), **metrics(y[test], pred, prob),
                              'fit_seconds': 0., 'best_params': '{}'})
                predictions.extend({'repeat': repeat, 'fold': fold, 'sample_id': int(i),
                                    'model': name, 'feature_set': '-', 'target': int(y[i]),
                                    'prediction': int(pred[j]), 'probability': float(prob[j])}
                                   for j, i in enumerate(test))
            # Checkpoint utile anche se un'esecuzione viene interrotta.
            write_csv(output / 'cv_folds.csv', folds)
    write_csv(output / 'predictions.csv', predictions)
    write_json(output / 'splits.json', manifest)
    summary = []
    for name, feature_set in sorted({(r['model'], r['feature_set']) for r in folds}):
        selected = [r for r in folds if (r['model'], r['feature_set']) == (name, feature_set)]
        result = {'model': name, 'feature_set': feature_set, 'n_folds': len(selected)}
        for metric in METRICS:
            values = [r[metric] for r in selected]
            result[f'{metric}_mean'] = float(np.mean(values))
            result[f'{metric}_std'] = float(np.std(values, ddof=1))
        summary.append(result)
    write_csv(output / 'cv_summary.csv', summary)
    deltas = []
    for name in model_configs(seed):
        by_key = {(r['repeat'], r['fold'], r['feature_set']): r for r in folds if r['model'] == name}
        for reference in ['BASE', 'BASE+LOCAL']:
            diffs = [by_key[(r, f, 'BASE+KB')]['f1_macro'] - by_key[(r, f, reference)]['f1_macro']
                     for r in range(config['repeats']) for f in range(config['outer'])]
            deltas.append({'model': name, 'comparison': f'BASE+KB minus {reference}',
                           'f1_delta_mean': float(np.mean(diffs)),
                           'f1_delta_std': float(np.std(diffs, ddof=1)),
                           'positive_folds': sum(d > 0 for d in diffs), 'n_folds': len(diffs)})
    write_csv(output / 'ablation_deltas.csv', deltas)
    return summary, deltas


def evaluate_planning(count, seed, output, rules):
    rng = np.random.default_rng(seed + 300)
    rows, cases = [], []
    for i in range(count):
        n = [8, 12, 16][i % 3]
        k = [2, 4, 6][(i // 3) % 3]
        topology = make_topology(rng, n)
        failed = set(map(str, rng.choice(topology.nodes, size=k, replace=False)))
        optimal = exhaustive_cost(topology, failed)
        cases.append({'case': i, 'topology': topology.to_dict(), 'failed': sorted(failed)})
        for strategy in ['ucs', 'cheapest']:
            result = plan(topology, failed, rules, strategy)
            valid = not simulate_down(topology, failed.difference(result.repairs)).intersection(topology.critical)
            if not valid or (strategy == 'ucs' and result.cost != optimal):
                raise AssertionError('Piano non valido o UCS non ottimale')
            rows.append({'case': i, 'n_nodes': n, 'n_failures': k, 'strategy': strategy,
                         **asdict(result), 'oracle_cost': optimal,
                         'excess_cost': result.cost - optimal, 'valid': int(valid)})
    write_csv(output / 'planning_cases.csv', rows)
    write_json(output / 'planning_inputs.json', cases)
    summary = []
    for strategy in ['ucs', 'cheapest']:
        for k in [2, 4, 6]:
            selected = [r for r in rows if r['strategy'] == strategy and r['n_failures'] == k]
            if not selected:
                continue
            item = {'strategy': strategy, 'n_failures': k, 'cases': len(selected)}
            for metric in ['cost', 'excess_cost', 'expanded', 'seconds', 'valid']:
                values = [r[metric] for r in selected]
                item[f'{metric}_mean'] = float(np.mean(values))
                item[f'{metric}_std'] = float(np.std(values, ddof=1)) if len(values) > 1 else 0.
            summary.append(item)
    write_csv(output / 'planning_summary.csv', summary)
    return summary


def run(profile, seed, output, scenario='standard'):
    config = {**PROFILES[profile], 'scenario': scenario, 'scenario_parameters': SCENARIOS[scenario]}
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    # Un manifesto incompleto non puo essere confuso con un run concluso.
    write_json(output / 'run.json', {'status': 'running', 'profile': profile, 'seed': seed, **config})
    started = perf_counter()
    rules = load_rules()
    print('Generazione dataset e verifica del ragionamento...', flush=True)
    rows, reasoning = build_dataset(config, seed, output, rules)
    from .prolog import materialize
    print('Inferenza SWI-Prolog e confronto completo con Datalog...', flush=True)
    rows, prolog_metadata = materialize(output, rules)
    from .unsupervised import evaluate as evaluate_unsupervised
    print('Regimi nominali K-Means, anomalie e propagazione nella KB...', flush=True)
    monitoring = evaluate_unsupervised(output, config, seed)
    print(f"Esempi: {len(rows)}, target positivo: {np.mean([r['target'] for r in rows]):.3f}", flush=True)
    with threadpool_limits(limits=1):
        summary, deltas = evaluate_ml(rows, config, seed, output)
    planning = evaluate_planning(config['planning_cases'], seed, output, rules)
    from .bayesian import evaluate as evaluate_bayesian
    from .analysis import evaluate as evaluate_analysis
    from .layout import export
    print('Rete bayesiana: struttura e parametri nei fold di training...', flush=True)
    with threadpool_limits(limits=1):
        bayesian = evaluate_bayesian(output, rows, seed)
    print('Curve a gruppi, importanze su test esterni e figure...', flush=True)
    evaluate_analysis(output, rows, seed)
    export(output)
    metadata = {'status': 'complete', 'profile': profile, 'seed': seed, **config,
                'samples': len(rows), 'prevalence': float(np.mean([r['target'] for r in rows])),
                'python': platform.python_version(), 'platform': platform.platform(),
                'numpy': np.__version__, 'scipy': scipy.__version__, 'sklearn': sklearn.__version__,
                'seconds': perf_counter() - started, 'feature_sets': FEATURE_SETS,
                'models': list(model_configs(seed)), 'baselines': ['DummyPrior', 'LogicOnly'],
                'prolog': prolog_metadata, 'bayesian': bayesian, 'monitoring': monitoring,
                'parameter_grids': {name: grid for name, (_, grid) in model_configs(seed).items()},
                'sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in sorted([*ROOT.glob('src/servicerescue/*.py'), *ROOT.glob('src/*.py'),
                                            ROOT / 'kb/rules.json', ROOT / 'kb/kb.pl',
                                            ROOT / 'requirements.txt', ROOT / 'main.py'])},
                'dataset_sha256': hashlib.sha256((output / 'dataset.csv').read_bytes()).hexdigest()}
    write_json(output / 'run.json', metadata)
    from .report import report
    report(output, metadata, summary, deltas, reasoning, planning)
    print(f"Completato: {output / 'REPORT.md'}", flush=True)
