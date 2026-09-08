"""Esporta dati, tabelle e figure nella struttura di consegna di ServiceRescue-KB."""
from pathlib import Path
import shutil
from .logic import ROOT

TABLES = {
    'cluster_profiles.csv': '01_cluster_profiles.csv',
    'cv_summary.csv': '02_nested_cv_ablation.csv',
    'bayesian_summary.csv': '03_bayesian_network_cv.csv',
    'learning_curve_summary.csv': '04_learning_curves.csv',
    'importance_summary.csv': '05_feature_importance.csv',
    'planning_summary.csv': '06_repair_search.csv',
    'monitoring_summary.csv': '07_anomaly_detection.csv',
    'silhouette_summary.csv': '08_silhouette_scores.csv',
    'reasoning_cases.csv': '09_kb_statistics.csv',
}


def export(output):
    output = Path(output)
    # I run alternativi restano autonomi senza sovrascrivere la consegna full.
    destination = ROOT if output.resolve() == (ROOT / 'results/full').resolve() else output / 'layout'
    raw, processed, tables = destination / 'data/raw', destination / 'data/processed', destination / 'results/tables'
    for directory in [raw, processed, tables]:
        directory.mkdir(parents=True, exist_ok=True)
    for name in ['topologies.json', 'observations.jsonl']:
        shutil.copyfile(output / name, raw / name)
    for name in ['monitoring_nominal.csv', 'monitoring_observed.csv']:
        shutil.copyfile(output / name, raw / name)
    for name, renamed in [('dataset.csv', 'service_with_kb_features.csv'), ('facts.pl', 'facts.pl')]:
        shutil.copyfile(output / name, processed / renamed)
    for name, renamed in TABLES.items():
        shutil.copyfile(output / name, tables / renamed)
    shutil.copyfile(output / 'monitoring_predictions.csv', processed / 'service_with_regime_alarms.csv')
    from .analysis import figures
    figures(output, destination / 'results/figures')
    from .unsupervised import plot_silhouette
    plot_silhouette(output, destination / 'results/figures')
