"""Riesegue la CV supervisionata sul dataset materializzato, in una cartella separata."""
from servicerescue.analysis import read_rows
from servicerescue.experiments import evaluate_ml, PROFILES
from servicerescue.logic import ROOT

if __name__ == '__main__':
    output = ROOT / 'results/supervised'
    output.mkdir(parents=True, exist_ok=True)
    rows = read_rows(ROOT / 'results/full/dataset.csv')
    rows = [{k: float(v) if k not in ('sample_id', 'group', 'snapshot', 'target') else int(v)
             for k, v in row.items()} for row in rows]
    evaluate_ml(rows, PROFILES['full'], 42, output)
    print(f'Risultati: {output}')
