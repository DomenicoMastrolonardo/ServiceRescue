"""Test semantici e oracoli indipendenti; eseguire con unittest discover."""
import itertools
import json
from pathlib import Path
import sys
import tempfile
import unittest
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from servicerescue.logic import infer, load_rules, unify
from servicerescue.domain import (Topology, demo_topology, make_topology,
                                 sample_observation, simulate_down)
from servicerescue.features import extract, FEATURE_SETS
from servicerescue.planning import plan, exhaustive_cost
from servicerescue.experiments import group_splits


class ReasoningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = load_rules()

    def test_multihop_explanation(self):
        closure = infer(demo_topology().facts({'power'}), self.rules)
        self.assertIn(('critical_down', 'portal'), closure.facts)
        self.assertIn(('reach', 'portal', 'power'), closure.facts)
        proof = json.dumps(closure.explain(('critical_down', 'portal')))
        self.assertIn('down_required', proof)
        self.assertIn('power', proof)

    def test_topology_scenario_extremes(self):
        # Due semantiche distinte: OR delle repliche e AND dei requisiti.
        redundant = make_topology(np.random.default_rng(7), 8, 1., 0.)
        dense = make_topology(np.random.default_rng(7), 8, 0., 1.)
        self.assertEqual(len(redundant.replicas), 5)
        self.assertEqual(redundant.requires, [])
        self.assertEqual(len(dense.requires), 10)
        self.assertEqual(dense.replicas, [])
        for topology in [redundant, dense]:
            for bits in itertools.product([False, True], repeat=3):
                failed = {s for s, active in zip(topology.nodes, bits) if active}
                actual = {s for s, in infer(topology.facts(failed), self.rules).query('down')}
                self.assertEqual(actual, simulate_down(topology, failed))

    def test_invalid_topology_parameters(self):
        for n, replica, extra in [(2, .5, .5), (8, -1, .5), (8, .5, 1.1)]:
            with self.assertRaises(ValueError):
                make_topology(np.random.default_rng(0), n, replica, extra)

    def test_replicas_require_both_failures(self):
        facts = [('replicas', 'app', 'a', 'b'), ('alarm', 'a')]
        one = infer(facts, self.rules)
        both = infer(facts + [('alarm', 'b')], self.rules)
        self.assertNotIn(('down', 'app'), one.facts)
        self.assertIn(('degraded', 'app'), one.facts)
        self.assertIn(('down', 'app'), both.facts)

    def test_shared_cause_breaks_redundancy(self):
        facts = [('replicas', 'app', 'a', 'b'), ('requires', 'a', 'power'),
                 ('requires', 'b', 'power'), ('alarm', 'power')]
        self.assertIn(('down', 'app'), infer(facts, self.rules).facts)

    def test_cycles_terminate_and_no_spontaneous_failure(self):
        facts = [('requires', 'a', 'b'), ('requires', 'b', 'a')]
        quiet = infer(facts, self.rules)
        alarm = infer(facts + [('alarm', 'a')], self.rules)
        self.assertEqual(quiet.query('down'), [])
        self.assertEqual(alarm.query('down'), [('a',), ('b',)])
        self.assertLess(alarm.rounds, 10)
        # Una prova finita non entra in ricorsione anche se il grafo e ciclico.
        json.dumps(alarm.explain(('down', 'b')))

    def test_unification_repeated_variable(self):
        self.assertIsNone(unify(('r', '?x', '?x'), ('r', 'a', 'b'), {}))
        self.assertEqual(unify(('r', '?x', '?x'), ('r', 'a', 'a'), {}), {'?x': 'a'})

    def test_ground_facts_and_safe_rules(self):
        with self.assertRaises(ValueError):
            infer([('alarm', '?x')], self.rules)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'rules.json'
            path.write_text(json.dumps([{'name': 'unsafe', 'head': ['p', '?x'], 'body': [['q', '?y']]}]))
            with self.assertRaises(ValueError):
                load_rules(path)

    def test_exhaustive_failure_subsets_against_oracle(self):
        rng = np.random.default_rng(121)
        for _ in range(3):
            topology = make_topology(rng, 6)
            for bits in itertools.product([False, True], repeat=6):
                failures = {s for s, active in zip(topology.nodes, bits) if active}
                closure = infer(topology.facts(failures), self.rules)
                self.assertEqual({s for s, in closure.query('down')}, simulate_down(topology, failures))

    def test_idempotence_and_rule_order(self):
        facts = demo_topology().facts({'power', 'db_b'})
        result = infer(facts, self.rules)
        self.assertEqual(result.facts, infer(result.facts, self.rules).facts)
        self.assertEqual(result.facts, infer(facts, tuple(reversed(self.rules))).facts)


class PlanningTests(unittest.TestCase):
    def test_greedy_counterexample(self):
        topology = demo_topology()
        rules = load_rules()
        optimal = plan(topology, {'power', 'db_b'}, rules)
        greedy = plan(topology, {'power', 'db_b'}, rules, 'cheapest')
        self.assertEqual(optimal.repairs, ['power'])
        self.assertEqual(optimal.cost, 4)
        self.assertEqual(greedy.cost, 6)

    def test_random_cases_against_exhaustive_search(self):
        rng = np.random.default_rng(51)
        for _ in range(20):
            topology = make_topology(rng, 8)
            failed = set(map(str, rng.choice(topology.nodes, 4, replace=False)))
            result = plan(topology, failed, load_rules())
            self.assertEqual(result.cost, exhaustive_cost(topology, failed))
            self.assertFalse(simulate_down(topology, failed.difference(result.repairs)) & set(topology.critical))

    def test_no_failures_and_invalid_cost(self):
        topology = demo_topology()
        self.assertEqual(plan(topology, set(), load_rules()).cost, 0)
        topology.costs['power'] = 0
        with self.assertRaises(ValueError):
            plan(topology, {'power'}, load_rules())

    def test_repair_one_of_two_replicas(self):
        topology = Topology(['a', 'b', 'app'], [], [['app', 'a', 'b']], ['app'],
                            {'a': 5, 'b': 2, 'app': 10}, {'a': 0, 'b': 1, 'app': 2})
        result = plan(topology, {'a', 'b'}, load_rules())
        self.assertEqual(result.repairs, ['b'])
        self.assertEqual(result.cost, 2)


class EvaluationTests(unittest.TestCase):
    def test_groups_disjoint_in_both_loops(self):
        y = np.tile([0, 1, 0, 1], 20)
        groups = np.repeat(np.arange(20), 4)
        coverage = []
        for train, test in group_splits(y, groups, 5, 42):
            self.assertFalse(set(groups[train]) & set(groups[test]))
            coverage.extend(test)
            for a, b in group_splits(y[train], groups[train], 3, 43):
                self.assertFalse(set(groups[train[a]]) & set(groups[train[b]]))
                self.assertFalse(set(groups[test]) & set(groups[train[b]]))
        self.assertEqual(sorted(coverage), list(range(len(y))))

    def test_features_do_not_use_target_and_are_reproducible(self):
        rng = np.random.default_rng(8)
        topology = make_topology(rng, 12)
        observation, _ = sample_observation(rng, topology)
        original, _ = extract(topology, observation, load_rules())
        # Anche un campo estraneo contenente il target deve essere ignorato.
        augmented = {s: {**v, 'target': 1} for s, v in observation.items()}
        changed, _ = extract(topology, augmented, load_rules())
        self.assertEqual(original, changed)
        self.assertEqual(set(original), set(FEATURE_SETS['BASE+KB']))
        self.assertTrue(all(np.isfinite(v) for v in original.values()))


if __name__ == '__main__':
    unittest.main()
