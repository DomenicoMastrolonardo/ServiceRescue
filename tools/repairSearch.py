"""Benchmark aggiuntivo di ricerca delle riparazioni."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from servicerescue.experiments import evaluate_planning
from servicerescue.logic import ROOT, load_rules

if __name__ == '__main__':
    output = ROOT / 'results/repair'
    output.mkdir(parents=True, exist_ok=True)
    evaluate_planning(60, 42, output, load_rules())
    print(f'Risultati: {output}')
