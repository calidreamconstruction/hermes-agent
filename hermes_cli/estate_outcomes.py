"""Hermes parent adapter to the estate's existing outcome contract.

Installed as hermes_cli.estate_outcomes because Hermes owns a different tools
package. The contract source stays tools/outcome.py in the registered estate.
"""
from functools import wraps, lru_cache
import importlib.util
import json
import os
from pathlib import Path
from copy import deepcopy


def parent_checked_async(fn):
    """Recheck delivery with dispatch-time acceptance, including batch children."""
    @wraps(fn)
    def checked(*args, **kwargs):
        assigned = deepcopy(kwargs.pop('outcome_contract', None))
        contracts = deepcopy(kwargs.pop('outcome_contracts', None))
        runner = kwargs['runner']
        def verified_runner():
            raw = runner()
            if isinstance(raw, dict) and isinstance(raw.get('results'), list):
                rows = raw['results']
                verified = [settle_result(row, contracts[i] if isinstance(contracts, list) and i < len(contracts) else None)
                            for i, row in enumerate(rows)]
                ok = bool(verified) and all(row['success'] for row in verified)
                return dict(raw, results=verified, success=ok,
                            status='COMPLETED_WITH_VERIFIED_RESULT' if ok else 'PARTIAL_CONTINUATION_REQUIRED')
            return settle_result(raw, assigned)
        return fn(*args, **dict(kwargs, runner=verified_runner))
    return checked

@lru_cache(maxsize=1)
def _core():
    root = Path(os.environ.get('FARESSYSTEM_ROOT', 'C:/FaresSystem' if os.name == 'nt' else '/opt/faressystem'))
    spec = importlib.util.spec_from_file_location('azani_parent_outcome', root/'tools/outcome.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def settle_result(result, assigned=None):
    core = _core()
    original = dict(result) if isinstance(result, dict) else {'state': 'failed', 'error': 'malformed child result'}
    claim = dict(original)
    summary = claim.get('summary') or claim.get('final_response')
    if isinstance(summary, str):
        try:
            structured = json.loads(summary)
        except (TypeError, ValueError):
            structured = None
        if isinstance(structured, dict):
            claim.update(structured)
    # Embedded prose/JSON cannot erase a transport failure or explicit no-op.
    if core.normalize(original) in (core.RETRY, core.TERMINAL, core.NO_WORK):
        claim['state'] = core.normalize(original)
    if original.get('success') is False or original.get('ok') is False:
        claim['success'] = False
    task = dict(assigned or {})
    task.setdefault('acceptance', ['assigned_child_acceptance'])
    task.update(kind='work', runnable_work=1)
    outcome = core.settle(task, claim, verifier=core.verify_acceptance)
    return dict(claim, execution_status=original.get('status'),
                status=outcome['state'], success=outcome['success'], outcome=outcome)


def parent_checked_child(fn):
    @wraps(fn)
    def checked(task_index, goal, child=None, parent_agent=None, **kwargs):
        result = fn(task_index, goal, child=child, parent_agent=parent_agent, **kwargs)
        return settle_result(result, getattr(child, '_estate_outcome_contract', None))
    return checked


def parent_checked_kanban(fn):
    @wraps(fn)
    def checked(conn, task_id, **kwargs):
        row = conn.execute('SELECT body, current_run_id, status FROM tasks WHERE id=?', (task_id,)).fetchone()
        if not row or row['status'] not in ('running', 'ready', 'blocked'):
            return False
        expected = kwargs.get('expected_run_id')
        if row['current_run_id'] is not None and expected is None:
            return False  # an unfenced caller cannot settle an owned run
        if expected is not None and row['current_run_id'] != expected:
            return False  # preserve another live owner's lease
        try:
            body = json.loads(row['body'] or '{}')
        except (TypeError, ValueError):
            body = {}
        assigned = body.get('outcome_contract', {}) if isinstance(body, dict) else {}
        claim = dict(kwargs.get('metadata') or {}, status='completed',
                     summary=kwargs.get('summary') or kwargs.get('result') or '')
        settled = settle_result(claim, assigned)
        if not settled['success']:
            # Existing task event store is the durable child-result rail. No
            # terminal-success write, no dependency release, no new queue.
            import time
            conn.execute('INSERT INTO task_events(task_id,run_id,kind,payload,created_at) VALUES (?,?,?,?,?)',
                         (task_id, row['current_run_id'], 'completion_rejected_unverified',
                          json.dumps(settled['outcome']), int(time.time())))
            conn.commit()
            from hermes_cli import kanban_db as kb
            outcome = settled['outcome']
            if outcome['state'] in ('FAILED_RETRYABLE', 'FAILED_TERMINAL'):
                kb._record_task_failure(conn, task_id, json.dumps(outcome),
                    outcome=outcome['state'], failure_limit=3,
                    release_claim=True, end_run=True)
            else:
                # Preserve exact continuation on the owning task and existing
                # event store; blocked here never means successful completion.
                if not outcome.get('wake_event'):
                    outcome['dependency'] = 'parent acceptance verifier for ' + task_id
                    outcome['wake_event'] = 'parent_verifier_available:' + task_id
                kb.block_task(conn, task_id, reason=json.dumps(outcome), expected_run_id=expected)
            return False
        metadata = dict(kwargs.get('metadata') or {}, parent_outcome=settled['outcome'])
        return fn(conn, task_id, **dict(kwargs, metadata=metadata))
    return checked
