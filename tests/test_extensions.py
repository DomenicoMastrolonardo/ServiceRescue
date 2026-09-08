import json
from pathlib import Path
import sys
import tempfile
import unittest
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from servicerescue.bayesian import BayesianNetwork
from servicerescue.logic import infer, load_rules
from servicerescue.prolog import query_batch, DERIVED


class PrologTests(unittest.TestCase):
    def test_real_engine_contexts_cycles_and_replica_conjunction(self):
        cases = [(0, [('requires', 'a', 'b'), ('requires', 'b', 'a'), ('alarm', 'a'), ('critical', 'b')]),
                 (1, [('requires', 'a', 'b'), ('requires', 'b', 'a')]),
                 (2, [('replicas', 's', 'a', 'b'), ('alarm', 'a')]),
                 (3, [('replicas', 's', 'a', 'b'), ('alarm', 'a'), ('alarm', 'b')])]
        with tempfile.TemporaryDirectory() as directory:
            actual, metadata = query_batch(cases, directory)
        self.assertIn('SWI-Prolog', metadata['engine'])
        for sample_id, facts in cases:
            self.assertEqual(actual[sample_id], {f for f in infer(facts, load_rules()).facts if f[0] in DERIVED})
        self.assertNotIn(('down', 'a'), actual[1])
        self.assertNotIn(('down', 's'), actual[2])
        self.assertIn(('down', 's'), actual[3])


class BayesianTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(38)
        self.y = np.tile([0, 1], 100)
        self.X = rng.random((200, 5))
        self.X[:, 0] = self.y
        self.model = BayesianNetwork().fit(self.X, self.y)

    def test_bic_learns_predictive_edge_and_parent_bound(self):
        self.assertIn(0, self.model.parents_[1])
        for node, parents in enumerate(self.model.parents_):
            self.assertLessEqual(len(parents), 2)
            self.assertTrue(all(p < node for p in parents))

    def test_joint_cpds_and_prior_normalized(self):
        self.assertAlmostEqual(float(self.model.joint_.sum()), 1.)
        for cpd in self.model.cpds_:
            np.testing.assert_allclose(cpd.sum(axis=-1), 1)
        np.testing.assert_allclose(self.model.query({}), [.5, .5], atol=1e-10)

    def test_partial_evidence_and_direct_prediction_agree(self):
        self.assertGreater(self.model.query({0: 1})[1], .9)
        row = self.X[4]
        states = (row > self.model.thresholds_).astype(int)
        np.testing.assert_allclose(self.model.query(dict(enumerate(states))), self.model.predict_proba([row])[0])

    def test_holdout_does_not_change_discretizer(self):
        thresholds = self.model.thresholds_.copy()
        self.model.predict_proba(np.full((4, 5), 1000.))
        np.testing.assert_array_equal(self.model.thresholds_, thresholds)
        np.testing.assert_allclose(thresholds, np.median(self.X, axis=0))

    def test_invalid_evidence_rejected(self):
        with self.assertRaises(ValueError):
            self.model.query({9: 1})
        with self.assertRaises(ValueError):
            self.model.query({0: 3})


if __name__ == '__main__':
    unittest.main()
