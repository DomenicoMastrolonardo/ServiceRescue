"""Riesegue la rete bayesiana sugli stessi split esterni del run completo."""
from servicerescue.analysis import read_rows
from servicerescue.bayesian import evaluate
from servicerescue.logic import ROOT

if __name__ == '__main__':
    output = ROOT / 'results/full'
    rows = read_rows(output / 'dataset.csv')
    rows = [{k: float(v) if k not in ('sample_id', 'group', 'snapshot', 'target') else int(v)
             for k, v in row.items()} for row in rows]
    print(evaluate(output, rows, 42))
