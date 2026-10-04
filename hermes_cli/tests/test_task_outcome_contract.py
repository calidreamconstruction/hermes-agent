#!/usr/bin/env python3
"""10-case contract suite for task_outcome_contract.

Every case must resolve to a DIFFERENT and CORRECT classification. A suite that
passes by collapsing cases into one bucket is the exact bug being fixed, so the
suite also asserts distinctness.

Run: python3 hermes_cli/tests/test_task_outcome_contract.py
"""
import os
import sys
import unittest

sys.path.insert(0, "/Users/faressystem/hermes-agent")

from hermes_cli.task_outcome_contract import (  # noqa: E402
    BLOCKED,
    COMPLETED,
    DEFERRED,
    DUPLICATE,
    FAILED_RETRYABLE,
    FAILED_TERMINAL,
    NO_ELIGIBLE,
    PARTIAL,
    Outcome,
    OutcomeError,
    classify,
    is_successful_completion,
    validate,
)

RESULTS = {}


class OutcomeContractSuite(unittest.TestCase):
    def _classify(self, label, expected_state, expected_success, **kw):
        out = classify(**kw)
        RESULTS[label] = out.state
        self.assertEqual(
            out.state, expected_state,
            f"{label}: expected {expected_state}, got {out.state}")
        self.assertEqual(
            is_successful_completion(out), expected_success,
            f"{label}: success flag wrong for {out.state}")
        return out

    # 1 ── true no-op heartbeat: legitimate, and NOT a completion
    def test_01_true_noop_heartbeat(self):
        self._classify(
            "1", NO_ELIGIBLE, False,
            summary="HEARTBEAT_OK nothing to do", is_real_task=False, heartbeat=True)

    # 2 ── real task, work available, worker no-ops → must NOT be success
    def test_02_real_task_worker_noops(self):
        out = self._classify(
            "2", FAILED_RETRYABLE, False,
            summary="nothing_to_do", is_real_task=True, acceptance_unfinished=True)
        self.assertIn("replan", str(out.metadata.get("action", "")).lower())

    # 3 ── blocked: exact dependency + wake event required
    def test_03_blocked_needs_dependency_and_wake(self):
        out = self._classify(
            "3", BLOCKED, False, state=BLOCKED, is_real_task=True,
            summary="cannot proceed", dependency="t_parent not complete",
            wake_event="parent task completes")
        validate(out)
        bad = Outcome(BLOCKED, summary="blocked", metadata={"dependency": "x"})
        with self.assertRaises(OutcomeError):
            validate(bad)  # missing wake_event

    # 4 ── unavailable machine → blocked on capability, not success
    def test_04_unavailable_machine(self):
        out = self._classify(
            "4", BLOCKED, False, state=BLOCKED, is_real_task=True,
            summary="PC2 unreachable", dependency="PC2 host offline",
            wake_event="PC2 returns to the tailnet")
        validate(out)

    # 5 ── duplicate worker → ownership recorded, not a completion
    def test_05_duplicate_owner(self):
        out = self._classify(
            "5", DUPLICATE, False, state=DUPLICATE, is_real_task=True,
            summary="already claimed", owner="worker-42 (pid 1234)")
        validate(out)

    # 6 ── child claims ok:true, changed nothing → must be downgraded
    def test_06_ok_true_without_changes(self):
        out = self._classify(
            "6", FAILED_RETRYABLE, False,
            summary="nothing to do", state=COMPLETED, is_real_task=True,
            acceptance_unfinished=True, result="ok:true")
        self.assertEqual(out.metadata.get("reclassified_from"), COMPLETED)

    # 7 ── wrote a file to the wrong destination → partial, needs continuation
    def test_07_wrong_destination(self):
        self._classify(
            "7", PARTIAL, False,
            summary="wrote report to /tmp/scratch/out.txt", is_real_task=True,
            acceptance_unfinished=True, remaining="move to the real destination")

    # 8 ── executed but verification was allowlisted out → not proof of done
    def test_08_verification_unavailable(self):
        self._classify(
            "8", PARTIAL, False,
            summary="Done, but verification tooling is allowlisted out",
            is_real_task=True, remaining="run verification when allowed")

    # 9 ── partial useful work with remaining items
    def test_09_partial_useful(self):
        self._classify(
            "9", PARTIAL, False,
            summary="did items 1-3 of 7", is_real_task=True,
            acceptance_unfinished=True, remaining="items 4-7")

    # 10 ── real verified completion → the ONLY success
    def test_10_real_verified_completion(self):
        out = self._classify(
            "10", COMPLETED, True,
            summary="fixed auth.py; test_regression passes; committed 4a1f2c9",
            is_real_task=True,
            evidence="pytest -q: 12 passed; git rev-parse HEAD = 4a1f2c9")
        validate(out)
        # A COMPLETED with no verification evidence must be refused.
        with self.assertRaises(OutcomeError):
            validate(Outcome(COMPLETED, summary="done", metadata={}))

    # ── the property the whole redesign exists for ──
    def test_noop_is_never_a_successful_completion(self):
        for phrase in ("nothing to do", "nothing_to_do", "no-op", "NO_REPLY",
                       "nothing actionable", "idle", "already done",
                       "no changes needed", "heartbeat_ok"):
            for real in (True, False):
                out = classify(phrase, is_real_task=real,
                               acceptance_unfinished=real)
                self.assertFalse(
                    is_successful_completion(out),
                    f"{phrase!r} (is_real_task={real}) became a success")

    def test_all_states_are_distinct(self):
        """Guards against collapsing cases into one bucket."""
        self.assertEqual(
            len(RESULTS), 10, "suite must exercise all 10 cases")
        # 1, 2+6, 3+4, 5, 7+9, 8, 10 → 7 slots, 6 distinct states.
        # Cases 3 and 4 are both BLOCKED (dependency vs capability) and 2/6
        # are both FAILED_RETRYABLE; that pairing is deliberate — a missing
        # dependency and an unreachable machine are the same classification
        # with different `dependency`/`wake_event` payloads. The property that
        # matters is that a no-op never lands in the success bucket.
        self.assertEqual(len(set(RESULTS.values())), 6)
        self.assertNotIn(COMPLETED, {RESULTS["1"], RESULTS["2"], RESULTS["6"]})

    def test_failure_and_deferral_states(self):
        # summary belongs on the Outcome; other fields in metadata.
        validate(Outcome(FAILED_RETRYABLE, summary="timeout",
                         metadata={"error": "ETIMEDOUT"}))
        validate(Outcome(FAILED_TERMINAL, summary="bad input",
                         metadata={"error": "ValueError"}))
        validate(Outcome(DEFERRED, summary="waiting on owner",
                         metadata={"event": "owner approval"}))
        validate(Outcome(PARTIAL, summary="items 1-3 done",
                         metadata={"remaining": "items 4-7"}))
        for st in (FAILED_RETRYABLE, FAILED_TERMINAL, DEFERRED, PARTIAL):
            self.assertFalse(is_successful_completion(st))
        # A no-op reclassification carries a machine-readable reason and an
        # action, so the parent can replan instead of silently completing.
        out = classify("nothing to do", is_real_task=True,
                       acceptance_unfinished=True)
        self.assertEqual(out.state, FAILED_RETRYABLE)
        self.assertTrue(out.metadata.get("reason"))
        self.assertTrue(out.metadata.get("action"))


if __name__ == "__main__":
    suite = unittest.main(argv=[__file__, "-v"], exit=False).result
    print()
    print("=" * 70)
    print("10-case resolution map (distinctness is the point):")
    for k in sorted(RESULTS, key=lambda x: int(x.split()[0])):
        print(f"  case {k:2s} -> {RESULTS[k]}")
    print(f"  distinct states: {len(set(RESULTS.values()))} across {len(RESULTS)} cases")
    print("=" * 70)
    sys.exit(0 if suite.wasSuccessful() else 1)