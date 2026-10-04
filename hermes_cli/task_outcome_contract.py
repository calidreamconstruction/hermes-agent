"""Task outcome contract — shared, reusable terminal classifications.

WHY THIS EXISTS
---------------
The kanban completion path proved (measured, `swarm/outcome_semantics_probe.py`,
all 10 probe cases) to accept EVERY one of these as a successful completion:

    nothing_to_do / ok:true / blocked dependency / duplicate owner /
    unavailable machine / wrong destination / unverifiable success / partial

`_gate_empty_completion` only requires non-empty *prose*. It cannot tell a real
verified completion from a child that did nothing and reported success. The
result: the estate looks productive while no work occurred.

THE CONTRACT
------------
A task may only reach a terminal state through an explicit, evidence-bearing
classification. The core rule:

    A NO-OP IS NOT A SUCCESSFUL TASK COMPLETION.

`NO_ELIGIBLE_WORK` is admissible only for a genuine heartbeat/idle poll whose
scope provably contains no actionable item — never for a real task with
unfinished acceptance criteria.

This module is intentionally a pure library with no scheduler, no queue, no
daemon and no I/O of its own, so every harness (Hermes, Claude Code, Codex,
opencode, goose, ralph, the swarm) can import the same semantics instead of
each inventing its own. It is the reusable piece; wiring it into a specific
queue is a separate, deliberate step.

TERMINAL CLASSIFICATIONS
------------------------
COMPLETED_WITH_VERIFIED_RESULT  work done AND evidence proves the destination changed
BLOCKED_WITH_EXACT_DEPENDENCY  cannot proceed; names the dependency and the wake event
NO_ELIGIBLE_WORK               genuine idle/heartbeat; scope provably has nothing actionable
DUPLICATE_ALREADY_OWNED        another worker holds the claim; not a completion
FAILED_RETRYABLE               attempt failed, retry may succeed
FAILED_TERMINAL                attempt failed, retry cannot help
DEFERRED_UNTIL_EVENT           intentionally waiting on a named external event
PARTIAL_CONTINUATION_REQUIRED  useful progress, unfinished acceptance criteria remain

Only COMPLETED_WITH_VERIFIED_RESULT is a successful task completion. The rest
are terminal-but-not-done, and each carries the evidence its class demands.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable

__all__ = [
    "Outcome",
    "OutcomeError",
    "NO_OP_TOKENS",
    "VERIFIED_CLAIM_MARKERS",
    "classify",
    "validate",
    "is_successful_completion",
    "required_fields",
]

COMPLETED = "COMPLETED_WITH_VERIFIED_RESULT"
BLOCKED = "BLOCKED_WITH_EXACT_DEPENDENCY"
NO_ELIGIBLE = "NO_ELIGIBLE_WORK"
DUPLICATE = "DUPLICATE_ALREADY_OWNED"
FAILED_RETRYABLE = "FAILED_RETRYABLE"
FAILED_TERMINAL = "FAILED_TERMINAL"
DEFERRED = "DEFERRED_UNTIL_EVENT"
PARTIAL = "PARTIAL_CONTINUATION_REQUIRED"

TERMINAL_STATES = frozenset({
    COMPLETED, BLOCKED, NO_ELIGIBLE, DUPLICATE,
    FAILED_RETRYABLE, FAILED_TERMINAL, DEFERRED, PARTIAL,
})

#: The ONLY state that counts as a successful task completion.
SUCCESS_STATES = frozenset({COMPLETED})

#: States that mean "not done" even though they are terminal.
NON_SUCCESS_STATES = TERMINAL_STATES - SUCCESS_STATES

#: Fields each classification must carry. `validate()` enforces these.
required_fields: dict[str, tuple[str, ...]] = {
    COMPLETED: ("summary", "evidence"),
    BLOCKED: ("dependency", "wake_event"),
    NO_ELIGIBLE: ("summary", "scope_proof"),
    DUPLICATE: ("owner",),
    FAILED_RETRYABLE: ("summary", "error"),
    FAILED_TERMINAL: ("summary", "error"),
    DEFERRED: ("event",),
    PARTIAL: ("summary", "remaining"),
}

# Phrases a model emits when it did nothing. Their presence in a completion
# claim is strong evidence of a no-op regardless of the declared outcome.
NO_OP_TOKENS = (
    "nothing to do", "nothing_to_do", "nothingtodo", "no-op", "noop",
    "no action needed", "no action required", "nothing actionable",
    "nothing to change", "no changes needed", "no changes made",
    "already done", "already complete", "already completed",
    "nothing required", "no work to do", "idle", "heartbeat_ok",
    "no_reply", "no reply", "nothing further", "all good",
    "verified nothing", "no-op:",
)

# Markers of an explicit verification claim in the evidence text.
VERIFIED_CLAIM_MARKERS = (
    "test", "tests", "pass", "passed", "passing", "assert", "verified",
    "verification", "readback", "read back", "confirmed", "http 200",
    "200 ok", "exit code 0", "exit 0", "built", "compiled", "installed",
    "committed", "sha", "diff", "grep", "query", "sql", "curl", "pid",
)

_ALNUM = re.compile(r"[^a-z0-9]+")


def _norm(text: Any) -> str:
    return _ALNUM.sub(" ", str(text or "").lower()).strip()


def _has_no_op_marker(*values: Any) -> bool:
    blob = _norm(" ".join(str(v) for v in values if v is not None))
    return any(_norm(tok) in blob for tok in NO_OP_TOKENS)


def _has_verified_marker(*values: Any) -> bool:
    blob = _norm(" ".join(str(v) for v in values if v is not None))
    return any(_norm(m) in blob for m in VERIFIED_CLAIM_MARKERS)


# Phrases that state verification did NOT happen, or was impossible. A worker
# saying "I could not verify because X" is the definition of a verification
# gap, and an allowlist that prevented verification is a GAP — never proof of
# completion. This check runs BEFORE the positive marker check precisely so the
# word "verification" inside "could not verify" can never be read as proof.
VERIFICATION_REFUTED_MARKERS = (
    "could not verify", "cannot verify", "can t verify", "unable to verify",
    "not verified", "unverified", "verification unavailable",
    "verification not available", "verification skipped",
    "verification was skipped", "verification blocked",
    "allowlisted out", "allowlist blocked", "not allowed to verify",
    "couldn t confirm", "no way to confirm", "did not verify",
    "didn t verify", "without verifying", "verification gap",
    "tooling unavailable", "no access to verify", "proof unavailable",
)


def _verification_refuted(*values: Any) -> bool:
    blob = _norm(" ".join(str(v) for v in values if v is not None))
    return any(_norm(m) in blob for m in VERIFICATION_REFUTED_MARKERS)


def _meaningful(value: Any) -> bool:
    """True when `value` carries real information, not a placeholder."""
    if value is None:
        return False
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return False
    if isinstance(value, (list, tuple, set)):
        return any(_meaningful(v) for v in value)
    if isinstance(value, dict):
        return any(_meaningful(v) for v in value.values())
    text = str(value).strip()
    if not text:
        return False
    if text.lower() in {"none", "null", "n/a", "na", "-", "unknown", "tbd"}:
        return False
    return True


class OutcomeError(ValueError):
    """Raised when a completion violates the outcome contract."""


@dataclass(frozen=True)
class Outcome:
    """A classified terminal state plus the evidence that justifies it."""

    state: str
    summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    # -- convenience -------------------------------------------------------
    @property
    def is_success(self) -> bool:
        return self.state in SUCCESS_STATES

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_STATES

    def get(self, key: str, default: Any = None) -> Any:
        return self.metadata.get(key, default)

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "summary": self.summary,
            "metadata": dict(self.metadata),
            "is_success": self.is_success,
        }

    def __str__(self) -> str:  # pragma: no cover - display helper
        return f"{self.state}: {self.summary}" if self.summary else self.state


def classify(
    summary: Any = "",
    *,
    state: str | None = None,
    is_real_task: bool = True,
    acceptance_unfinished: bool = False,
    heartbeat: bool = False,
    **metadata: Any,
) -> Outcome:
    """Classify a worker's return into a terminal classification.

    The safety property: when a worker reports a no-op on a real task, this
    returns a non-success state. A caller can never accidentally treat it as a
    completed task, because `is_success` is False and `validate()` raises.

    Parameters
    ----------
    is_real_task
        False only for a genuine heartbeat/idle poll (no assigned scope).
    acceptance_unfinished
        True when the task has acceptance criteria that are not yet met.
    heartbeat
        True when the caller is a liveness ping with no task at all.
    """
    meta = {k: v for k, v in metadata.items() if v is not None}
    no_op = _has_no_op_marker(summary, *meta.values())

    # An explicit, legal declaration is honoured — but a no-op declaration on a
    # real task is downgraded rather than trusted.
    if state and state in TERMINAL_STATES:
        if state == COMPLETED and no_op and (is_real_task or acceptance_unfinished):
            return Outcome(
                FAILED_RETRYABLE,
                summary=str(summary or ""),
                metadata={
                    **meta,
                    "reclassified_from": COMPLETED,
                    "reason": (
                        "worker reported a no-op while declaring successful "
                        "completion; a no-op is not a successful completion"
                    ),
                    "action": "replan or return the correct terminal classification",
                },
            )
        return Outcome(state, summary=str(summary or ""), metadata=meta)

    # Inference when the caller gave no explicit state.
    if heartbeat and not is_real_task:
        return Outcome(NO_ELIGIBLE, summary=str(summary or ""),
                       metadata={**meta, "inferred": "heartbeat"})
    if no_op:
        if is_real_task or acceptance_unfinished:
            return Outcome(
                FAILED_RETRYABLE,
                summary=str(summary or ""),
                metadata={
                    **meta,
                    "inferred": "no-op on a real task",
                    "reason": (
                        "a real task with unfinished acceptance criteria cannot "
                        "be NO_ELIGIBLE_WORK; runnable work existed inside the "
                        "assigned scope"
                    ),
                    "action": "replan, or report the true blocker via BLOCKED_WITH_EXACT_DEPENDENCY",
                },
            )
        return Outcome(NO_ELIGIBLE, summary=str(summary or ""),
                       metadata={**meta, "inferred": "idle"})

    # Non-empty prose with no explicit state: only a success if it claims
    # verification. Otherwise it is partial — we cannot prove completion.
    if acceptance_unfinished:
        return Outcome(PARTIAL, summary=str(summary or ""),
                       metadata={**meta, "inferred": "acceptance criteria unfinished"})
    if _verification_refuted(summary, *meta.values()):
        return Outcome(PARTIAL, summary=str(summary or ""),
                       metadata={**meta, "inferred": "verification was not available"})
    if _has_verified_marker(summary, *meta.values()):
        return Outcome(COMPLETED, summary=str(summary or ""),
                       metadata={**meta, "inferred": "verification marker present"})
    return Outcome(PARTIAL, summary=str(summary or ""),
                   metadata={**meta, "inferred": "no verification evidence supplied"})


def validate(outcome: Outcome | str, **metadata: Any) -> Outcome:
    """Enforce per-state required fields. Raises OutcomeError when unsatisfied."""
    if isinstance(outcome, str):
        outcome = Outcome(outcome, metadata=dict(metadata))
    if outcome.state not in TERMINAL_STATES:
        raise OutcomeError(
            f"unknown terminal state {outcome.state!r}; expected one of "
            f"{sorted(TERMINAL_STATES)}")
    if outcome.state == COMPLETED and not _has_verified_marker(
            outcome.summary, *outcome.metadata.values()):
        raise OutcomeError(
            "COMPLETED_WITH_VERIFIED_RESULT requires evidence that the "
            "destination changed (a test run, readback, exit code, or "
            "equivalent). Use PARTIAL_CONTINUATION_REQUIRED when the work is "
            "not provably finished.")
    for field_name in required_fields.get(outcome.state, ()):
        # `summary` lives on the Outcome itself; every other required field is
        # carried in metadata. Reading metadata['summary'] alone silently
        # failed every legitimate completion.
        value = (outcome.summary if field_name == "summary"
                 else outcome.metadata.get(field_name))
        if not _meaningful(value):
            raise OutcomeError(
                f"{outcome.state} requires a meaningful {field_name!r}; got "
                f"{value!r}")
    return outcome


def is_successful_completion(outcome: Outcome | str) -> bool:
    """The single question callers should ask before recording a completion."""
    state = outcome.state if isinstance(outcome, Outcome) else str(outcome)
    return state in SUCCESS_STATES