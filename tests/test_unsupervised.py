"""Verifiche della separazione fra riferimento, calibrazione e test del monitoraggio."""
from pathlib import Path
import sys
import unittest
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from servicerescue.domain import demo_topology, simulate_down
from servicerescue.unsupervised import RegimeDetector, monitoring_data, monitoring_splits, distances


class MonitoringTests(unittest.TestCase):
    def test_group_splits_cover_test_and_isolate_calibration(self):
        groups = np.repeat(np.arange(30), 10)
        splits = list(monitoring_splits(groups, 5, 2, 42))
        for s in splits:
            fit, cal, test = (set(s[k]) for k in ['fit_groups', 'calibration_groups', 'test_groups'])
            self.assertFalse(fit & cal or fit & test or cal & test)
            self.assertEqual(fit | cal | test, set(groups))
        for repeat in range(2):
            self.assertEqual(sorted(g for s in splits if s['repeat'] == repeat for g in s['test_groups']), list(range(30)))

    def test_predictions_do_not_refit_and_calibration_is_separate(self):
        rng = np.random.default_rng(9)
        reference = np.vstack([rng.normal(0, .1, (80, 3)), rng.normal(4, .1, (80, 3))])
        calibration = rng.normal(2, 1, (30, 3))
        model = RegimeDetector(ks=[2, 3]).fit(reference, calibration)
        np.testing.assert_allclose(model.scaler_.mean_, reference.mean(axis=0))
        expected = np.quantile(distances(model.scaler_.transform(calibration), model.centers_), .95)
        self.assertAlmostEqual(model.thresholds_['KMeans'], expected)
        before = model.state()
        model.predict(np.full((3, 3), 100.))
        self.assertEqual(before, model.state())
        self.assertEqual(model.k_, 2)

    def test_monitoring_truth_is_separate_and_propagated(self):
        topology = demo_topology()
        reference, observed, truth = monitoring_data([topology], 50, 12)
        self.assertFalse({'target', 'failed', 'regime'} & set(reference[0]))
        self.assertFalse({'target', 'failed', 'regime'} & set(observed[0]))
        self.assertEqual((reference, observed, truth), monitoring_data([topology], 50, 12))
        self.assertTrue(any(t['failed'] for t in truth))
        for item in truth:
            self.assertEqual(item['critical_down'], int(bool(simulate_down(topology, item['failed']).intersection(topology.critical))))

    def test_nonfinite_reference_rejected(self):
        with self.assertRaises(ValueError):
            RegimeDetector().fit(np.full((12, 3), np.nan), np.ones((4, 3)))
