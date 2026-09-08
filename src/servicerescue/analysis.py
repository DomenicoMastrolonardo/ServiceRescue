"""Curve a gruppi e importanze su test esterni; figure da statistiche aggregate."""
import csv
import json
import os
from pathlib import Path
import tempfile
import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits
from .features import FEATURE_SETS


def read_rows(path):
    with Path(path).open(encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def fixed_models(seed):
    return {
        'LogisticRegression': make_pipeline(StandardScaler(), LogisticRegression(C=1., class_weight='balanced', max_iter=2000, random_state=seed)),
        'RandomForest': RandomForestClassifier(n_estimators=60, max_depth=4, min_samples_leaf=3, random_state=seed),
        'GradientBoosting': GradientBoostingClassifier(n_estimators=60, max_depth=2, learning_rate=.05, random_state=seed),
    }


def evaluate(output, rows, seed):
    from .experiments import write_csv
    output = Path(output)
    columns = FEATURE_SETS['BASE+KB']
    X = np.array([[r[c] for c in columns] for r in rows], dtype=float)
    y = np.array([r['target'] for r in rows], dtype=int)
    groups = np.array([r['group'] for r in rows], dtype=int)
    splits = json.loads((output / 'splits.json').read_text())
    curves, importances = [], []
    with threadpool_limits(limits=1):
        for split in splits:
            train, test = np.array(split['train_ids']), np.array(split['test_ids'])
            rng = np.random.default_rng(seed + 400 + split['repeat'] * 10 + split['fold'])
            ordered_groups = rng.permutation(np.unique(groups[train]))
            for fraction in [.4, .7, 1.]:
                selected = ordered_groups[:max(2, int(len(ordered_groups) * fraction))]
                subset = train[np.isin(groups[train], selected)]
                if len(np.unique(y[subset])) != 2:
                    raise ValueError('Sottoinsieme della curva con una sola classe')
                for name, estimator in fixed_models(seed).items():
                    estimator.fit(X[subset], y[subset])
                    curves.append({'repeat': split['repeat'], 'fold': split['fold'], 'model': name,
                                   'fraction': fraction, 'n_train': len(subset),
                                   'train_f1': float(f1_score(y[subset], estimator.predict(X[subset]), average='macro')),
                                   'test_f1': float(f1_score(y[test], estimator.predict(X[test]), average='macro'))})
                    if fraction == 1.:
                        permutation = permutation_importance(estimator, X[test], y[test],
                                                              scoring='f1_macro', n_repeats=3,
                                                              random_state=seed + split['fold'], n_jobs=1)
                        importances.extend({'repeat': split['repeat'], 'fold': split['fold'], 'model': name,
                                            'feature': c, 'f1_decrease': float(permutation.importances_mean[j])}
                                           for j, c in enumerate(columns))
    write_csv(output / 'learning_curve_folds.csv', curves)
    write_csv(output / 'importance_folds.csv', importances)
    curve_summary, importance_summary = [], []
    for name in fixed_models(seed):
        for fraction in [.4, .7, 1.]:
            selected = [r for r in curves if r['model'] == name and r['fraction'] == fraction]
            row = {'model': name, 'fraction': fraction, 'n_folds': len(selected)}
            for metric in ['n_train', 'train_f1', 'test_f1']:
                values = [r[metric] for r in selected]
                row[metric + '_mean'] = float(np.mean(values))
                row[metric + '_std'] = float(np.std(values, ddof=1))
            curve_summary.append(row)
        for feature in columns:
            values = [r['f1_decrease'] for r in importances if r['model'] == name and r['feature'] == feature]
            importance_summary.append({'model': name, 'feature': feature, 'n_folds': len(values),
                                       'f1_decrease_mean': float(np.mean(values)),
                                       'f1_decrease_std': float(np.std(values, ddof=1))})
    write_csv(output / 'learning_curve_summary.csv', curve_summary)
    write_csv(output / 'importance_summary.csv', importance_summary)


def figures(output, destination):
    os.environ.setdefault('MPLCONFIGDIR', str(Path(tempfile.gettempdir()) / 'servicerescue-matplotlib'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    output, destination = Path(output), Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    summary = read_rows(output / 'cv_summary.csv')
    names = list(fixed_models(42))
    fig, ax = plt.subplots(figsize=(9, 5))
    for j, feature_set in enumerate(FEATURE_SETS):
        selected = [next(r for r in summary if r['model'] == n and r['feature_set'] == feature_set) for n in names]
        ax.bar(np.arange(3) + (j - 1) * .25, [float(r['f1_macro_mean']) for r in selected], width=.25,
               yerr=[float(r['f1_macro_std']) for r in selected], capsize=3, label=feature_set)
    ax.set(xticks=np.arange(3), xticklabels=['Logistica', 'Random Forest', 'Gradient Boosting'],
           ylabel='F1 macro: media ± dev. standard', ylim=(0, 1))
    ax.legend()
    fig.tight_layout()
    fig.savefig(destination / '02_ablation_comparison.png', dpi=160)
    plt.close(fig)
    curves = read_rows(output / 'learning_curve_summary.csv')
    fig, axes = plt.subplots(1, 3, figsize=(13, 4), sharey=True)
    for ax, name in zip(axes, names):
        selected = [r for r in curves if r['model'] == name]
        for metric, label in [('train_f1', 'Training'), ('test_f1', 'Test esterno')]:
            ax.errorbar([float(r['n_train_mean']) for r in selected], [float(r[metric + '_mean']) for r in selected],
                        yerr=[float(r[metric + '_std']) for r in selected], marker='o', capsize=3, label=label)
        ax.set(title=name, xlabel='Osservazioni di training', ylim=(0, 1))
        ax.legend()
    axes[0].set_ylabel('F1 macro: media ± dev. standard')
    fig.tight_layout()
    fig.savefig(destination / '04_learning_curves.png', dpi=160)
    plt.close(fig)
    importance = read_rows(output / 'importance_summary.csv')
    fig, axes = plt.subplots(1, 3, figsize=(15, 7))
    for ax, name in zip(axes, names):
        selected = sorted([r for r in importance if r['model'] == name], key=lambda r: float(r['f1_decrease_mean']))
        ax.barh([r['feature'] for r in selected], [float(r['f1_decrease_mean']) for r in selected],
                xerr=[float(r['f1_decrease_std']) for r in selected], capsize=2)
        ax.set(title=name, xlabel='Riduzione F1 su test per permutazione')
    fig.tight_layout()
    fig.savefig(destination / '05_feature_importance.png', dpi=160)
    plt.close(fig)
    networks = json.loads((output / 'bayesian_networks.json').read_text())
    nodes = networks[0]['nodes']
    positions = {n: (np.cos(2 * np.pi * i / len(nodes)), np.sin(2 * np.pi * i / len(nodes))) for i, n in enumerate(nodes)}
    fig, ax = plt.subplots(figsize=(9, 7))
    # Frequenza degli archi fra tutti i fold, non uno specifico grafo finale.
    for a in nodes:
        for b in nodes:
            count = sum([a, b] in network['edges'] for network in networks)
            if count:
                ax.annotate('', xy=positions[b], xytext=positions[a],
                            arrowprops={'arrowstyle': '->', 'alpha': .25 + .75 * count / len(networks), 'color': '#2E5AAC'})
                mid = (np.array(positions[a]) + positions[b]) / 2
                ax.text(*mid, f'{count}/{len(networks)}', fontsize=8)
    for n, (x, y) in positions.items():
        ax.text(x, y, n, ha='center', va='center', bbox={'boxstyle': 'round', 'fc': '#E4ECF8', 'ec': '#2E5AAC'})
    ax.set(xlim=(-1.5, 1.6), ylim=(-1.35, 1.35), title='Archi appresi: frequenza nei fold esterni')
    ax.axis('off')
    fig.tight_layout()
    fig.savefig(destination / '03_bayesian_network.png', dpi=160)
    plt.close(fig)
