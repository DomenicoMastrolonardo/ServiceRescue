"""Rete discreta con struttura appresa via BIC entro un ordine prefissato.

Sei variabili binarie, al massimo due genitori; inferenza esatta per enumerazione.
La direzione degli archi e statistica e non identifica relazioni causali.
"""
from itertools import combinations, product
import json
from pathlib import Path
import numpy as np
from scipy.special import logsumexp, xlogy
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.model_selection import GridSearchCV
from sklearn.utils.validation import check_is_fitted, check_X_y, check_array

FEATURES = ['root_errors', 'mean_errors', 'root_down', 'exposed_fraction', 'degraded_fraction']
NAMES = ['future_down', *FEATURES]


class BayesianNetwork(ClassifierMixin, BaseEstimator):
    def __init__(self, alpha=1., max_parents=2):
        self.alpha = alpha
        self.max_parents = max_parents

    @staticmethod
    def counts(data, node, parents):
        table = np.zeros((2,) * (len(parents) + 1))
        np.add.at(table, tuple(data[:, j] for j in [*parents, node]), 1)
        return table

    def fit(self, X, y):
        X, y = check_X_y(X, y)
        if self.alpha <= 0 or self.max_parents not in (1, 2):
            raise ValueError('alpha > 0 e max_parents in {1,2} richiesti')
        self.classes_ = np.unique(y)
        if not np.array_equal(self.classes_, [0, 1]):
            raise ValueError('Sono richieste le classi 0 e 1')
        self.n_features_in_ = X.shape[1]
        self.thresholds_ = np.median(X, axis=0)
        data = np.column_stack([y, (X > self.thresholds_).astype(int)]).astype(int)
        self.parents_, self.cpds_, self.bic_scores_ = [], [], []
        for node in range(data.shape[1]):
            options = []
            for size in range(min(node, self.max_parents) + 1):
                for parents in combinations(range(node), size):
                    counts = self.counts(data, node, parents)
                    totals = counts.sum(axis=-1, keepdims=True)
                    probabilities = np.divide(counts, totals, out=np.zeros_like(counts), where=totals > 0)
                    score = float(xlogy(counts, probabilities).sum() - .5 * (2 ** size) * np.log(len(data)))
                    options.append((score, parents, counts))
            score, parents, counts = max(options, key=lambda r: r[0])
            self.parents_.append(parents)
            self.cpds_.append((counts + self.alpha) / (counts.sum(axis=-1, keepdims=True) + 2 * self.alpha))
            self.bic_scores_.append(score)
        self.assignments_ = np.array(list(product([0, 1], repeat=data.shape[1])), dtype=int)
        self.joint_ = np.exp(self._log_joint(self.assignments_))
        if not np.isclose(self.joint_.sum(), 1):
            raise AssertionError('Distribuzione congiunta non normalizzata')
        return self

    def _log_joint(self, data):
        result = np.zeros(len(data))
        for node, (parents, cpd) in enumerate(zip(self.parents_, self.cpds_)):
            result += np.log(cpd[tuple(data[:, j] for j in [*parents, node])])
        return result

    def predict_proba(self, X):
        check_is_fitted(self, 'cpds_')
        X = check_array(X)
        if X.shape[1] != self.n_features_in_:
            raise ValueError('Numero di feature errato')
        discrete = (X > self.thresholds_).astype(int)
        logp = np.column_stack([self._log_joint(np.column_stack([np.full(len(X), y), discrete])) for y in [0, 1]])
        return np.exp(logp - logsumexp(logp, axis=1, keepdims=True))

    def predict(self, X):
        return self.predict_proba(X).argmax(axis=1)

    def query(self, evidence):
        """evidence: indice della feature -> stato binario; omesse = marginalizzate."""
        check_is_fitted(self, 'joint_')
        selected = np.ones(len(self.assignments_), dtype=bool)
        for index, state in evidence.items():
            if index not in range(self.n_features_in_) or state not in (0, 1):
                raise ValueError('Evidenza fuori dominio')
            selected &= self.assignments_[:, index + 1] == state
        masses = np.array([self.joint_[selected & (self.assignments_[:, 0] == y)].sum() for y in [0, 1]])
        return masses / masses.sum()


def evaluate(output, rows, seed):
    from .experiments import metrics, write_csv, write_json, METRICS
    output = Path(output)
    X = np.array([[r[f] for f in FEATURES] for r in rows], dtype=float)
    y = np.array([r['target'] for r in rows])
    splits = json.loads((output / 'splits.json').read_text())
    folds, predictions, networks = [], [], []
    for split in splits:
        train, test = np.array(split['train_ids']), np.array(split['test_ids'])
        local = {int(global_id): i for i, global_id in enumerate(train)}
        inner = [(np.array([local[i] for i in s['train_ids']]), np.array([local[i] for i in s['validation_ids']]))
                 for s in split['inner']]
        search = GridSearchCV(BayesianNetwork(), {'alpha': [.5, 1., 2.], 'max_parents': [1, 2]},
                              cv=inner, scoring='f1_macro', error_score='raise', n_jobs=1)
        search.fit(X[train], y[train])
        model = search.best_estimator_
        probability = model.predict_proba(X[test])[:, 1]
        prediction = model.predict(X[test])
        folds.append({'repeat': split['repeat'], 'fold': split['fold'],
                      **metrics(y[test], prediction, probability),
                      'edges': sum(map(len, model.parents_)), 'best_params': json.dumps(search.best_params_)})
        predictions.extend({'repeat': split['repeat'], 'fold': split['fold'], 'sample_id': int(i),
                            'target': int(y[i]), 'prediction': int(prediction[j]), 'probability': float(probability[j])}
                           for j, i in enumerate(test))
        networks.append({'repeat': split['repeat'], 'fold': split['fold'], 'nodes': NAMES,
                         'thresholds': model.thresholds_.tolist(),
                         'edges': [[NAMES[p], NAMES[n]] for n, parents in enumerate(model.parents_) for p in parents],
                         'parents': [list(p) for p in model.parents_], 'cpds': [c.tolist() for c in model.cpds_],
                         'prior': model.query({}).tolist(),
                         'query': {'evidence': {'root_down': 1, 'exposed_fraction': 1},
                                   'posterior': model.query({2: 1, 3: 1}).tolist()}})
    summary = {'model': 'BayesianNetwork', 'n_folds': len(folds)}
    for metric in [*METRICS, 'edges']:
        vals = [r[metric] for r in folds]
        summary[metric + '_mean'] = float(np.mean(vals))
        summary[metric + '_std'] = float(np.std(vals, ddof=1))
    write_csv(output / 'bayesian_folds.csv', folds)
    write_csv(output / 'bayesian_predictions.csv', predictions)
    write_csv(output / 'bayesian_summary.csv', [summary])
    write_json(output / 'bayesian_networks.json', networks)
    return summary
