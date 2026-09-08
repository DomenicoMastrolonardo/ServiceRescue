"""Datalog positivo finito: join, punto fisso sincrono, prima prova aciclica.

Il motore interpreta regole esterne; non codifica la propagazione nel codice.
Non implementa Prolog, negazione, simboli funzione o OWL.
"""
from collections import defaultdict
from dataclasses import dataclass
import json
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Rule:
    name: str
    head: tuple
    body: tuple


def variable(term):
    return isinstance(term, str) and term.startswith("?")


def load_rules(path=None):
    raw = json.loads((Path(path) if path else ROOT / "kb/rules.json").read_text())
    rules = tuple(Rule(r["name"], tuple(r["head"]), tuple(map(tuple, r["body"]))) for r in raw)
    arities = {}
    for rule in rules:
        bound = {t for a in rule.body for t in a[1:] if variable(t)}
        if not rule.body or not {t for t in rule.head[1:] if variable(t)} <= bound:
            raise ValueError(f"Regola non range-restricted: {rule.name}")
        for atom in (rule.head, *rule.body):
            if not atom or not isinstance(atom[0], str) or variable(atom[0]):
                raise ValueError("Predicato non valido")
            if arities.setdefault(atom[0], len(atom) - 1) != len(atom) - 1:
                raise ValueError(f"Arita incoerente: {atom[0]}")
    return rules


def unify(pattern, fact, bindings):
    if len(pattern) != len(fact) or pattern[0] != fact[0]:
        return None
    result = dict(bindings)
    for term, value in zip(pattern[1:], fact[1:]):
        if variable(term):
            if term in result and result[term] != value:
                return None
            result[term] = value
        elif term != value:
            return None
    return result


@dataclass
class Closure:
    facts: set
    proofs: dict
    rounds: int
    matches: int
    seconds: float

    def query(self, predicate):
        return sorted(f[1:] for f in self.facts if f[0] == predicate)

    def explain(self, fact):
        fact = tuple(fact)
        if fact not in self.facts:
            return {"fact": fact, "entailed": False}
        rule, premises = self.proofs[fact]
        return {"fact": fact, "rule": rule,
                "premises": [self.explain(p) for p in premises]}


def infer(facts, rules=None):
    rules = load_rules() if rules is None else rules
    started = perf_counter()
    known = set(map(tuple, facts))
    if any(variable(t) for f in known for t in f):
        raise ValueError("I fatti devono essere ground")
    proofs = {f: ("input", ()) for f in known}
    rounds = matches = 0
    while True:
        by_pred = defaultdict(list)
        for fact in sorted(known):
            by_pred[fact[0]].append(fact)
        additions = {}
        for rule in rules:
            partial = [({}, ())]
            for atom in rule.body:
                joined = []
                for bindings, premises in partial:
                    for fact in by_pred[atom[0]]:
                        matches += 1
                        new = unify(atom, fact, bindings)
                        if new is not None:
                            joined.append((new, (*premises, fact)))
                partial = joined
                if not partial:
                    break
            for bindings, premises in partial:
                head = tuple(bindings[t] if variable(t) else t for t in rule.head)
                if head not in known:
                    additions.setdefault(head, (rule.name, premises))
        if not additions:
            break
        known.update(additions)
        proofs.update(additions)
        rounds += 1
    return Closure(known, proofs, rounds, matches, perf_counter() - started)
