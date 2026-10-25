"""
experiments.py - the register of every test run so far, and the significance bar that follows from it.

Every extra test run on the same data raises the chance that something passes by luck. This file counts them
and turns the count into a stricter t-threshold (Bonferroni, two-sided, family-wise 5%).
Add a row to experiments.json BEFORE running any new test.
"""
import json
import os
from statistics import NormalDist

PATH = "experiments.json"


def required_t(trials, alpha=0.05):
    """t-threshold so that, across `trials` tests, the chance of any false pass stays near alpha."""
    trials = max(int(trials), 1)
    return NormalDist().inv_cdf(1 - alpha / (2 * trials))


def load(path=PATH):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def total_trials(reg):
    return sum(int(e["trials"]) for e in reg["experiments"])


def main():
    reg = load()
    n = total_trials(reg)
    print(f"{n} tests so far; honest t-bar is about {required_t(n):.2f}")
    for e in reg["experiments"]:
        print(f"- {e['date']}  {e['name']}: {e['trials']} trials, {e['outcome']}")


if __name__ == "__main__":
    main()
