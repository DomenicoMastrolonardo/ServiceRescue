"""Curve e importanze diagnostiche, senza selezione di feature sui test."""
from servicerescue.analysis import read_rows, evaluate
from servicerescue.layout import export
from servicerescue.logic import ROOT

if __name__ == '__main__':
    output = ROOT / 'results/full'
    evaluate(output, read_rows(output / 'dataset.csv'), 42)
    export(output)
    print(f'Tabelle e figure: {ROOT / "results"}')
