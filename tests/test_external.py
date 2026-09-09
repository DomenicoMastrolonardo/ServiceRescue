import importlib.util
from pathlib import Path
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('external_evaluation', ROOT / 'tools/external/evaluate.py')
external = importlib.util.module_from_spec(spec)
spec.loader.exec_module(external)


class ExternalTests(unittest.TestCase):
    def test_temporal_partitions_reserve_nominal_and_fault_test(self):
        fit, cal, test = external.temporal_split(np.arange(150), 100)
        np.testing.assert_array_equal(fit, np.arange(60))
        np.testing.assert_array_equal(cal, np.arange(60, 80))
        np.testing.assert_array_equal(test, np.arange(80, 150))
        with self.assertRaises(ValueError):
            external.temporal_split(np.arange(150), 150)

    def test_missing_and_constant_features_use_training_only(self):
        X = np.array([[1., np.nan, 4.], [3., np.nan, 4.], [np.nan, np.nan, 4.]])
        state = external.preprocess_fit(X)
        self.assertEqual(state['keep'], [0, 2])
        self.assertEqual(state['medians'], [2., 4.])
        Z = external.transform(np.array([[np.nan, 100., 5.], [100., 200., 4.]]), state)
        self.assertEqual(Z.shape, (2, 2))
        self.assertEqual(Z[0, 0], 0.)
        self.assertEqual(Z[0, 1], 1.)
        self.assertEqual(state['medians'], [2., 4.])

    def test_call_graph_explains_possible_effects_without_deducing_down(self):
        rules = external.load_rules(ROOT / 'kb/observed_calls.json')
        facts = [('calls', 'frontend', 'api'), ('calls', 'api', 'db'),
                 ('calls', 'db', 'api'), ('sensor_alarm', 'db')]
        closure = external.infer(facts, rules)
        self.assertIn(('frontend',), closure.query('possibly_affected'))
        self.assertEqual(closure.query('down'), [])
        self.assertEqual(closure.query('critical_down'), [])
        self.assertEqual(closure.explain(('possibly_affected', 'frontend'))['rule'], 'possible_impact')


if __name__ == '__main__':
    unittest.main()
