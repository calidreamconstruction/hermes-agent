"""Owner compound scope must survive deterministic native handoff grounding."""
import copy
from agent.context_compressor import ContextCompressor, HISTORICAL_TASK_HEADING, _build_verbatim_user_section

def test_compound_source_order_and_long_requirement_survive():
    first='Audit ALL machines. '+('required component; '*900)+' FINAL_EXACT_MODEL_AT_ENDPOINT'
    turns=[{'role':'user','content':first},{'role':'assistant','content':'Proposal: replace model.'},{'role':'user','content':'Do not replace the router.'}]
    original=copy.deepcopy(turns)
    summary=HISTORICAL_TASK_HEADING+'\nOnly last correction.\n\n## Remaining\nUnverified work remains.'
    out=ContextCompressor._ground_historical_task_snapshot(summary,turns)
    assert first in out and turns[-1]['content'] in out
    assert out.index(first)<out.index(turns[-1]['content'])
    assert 'Proposal: replace model' not in out and turns==original
    assert 'Unverified work remains.' in out
    assert 'cancellation' in out and 'not a fresh instruction' in out

def test_lean_excerpt_cannot_claim_full_owner_coverage():
    turns=[{'role':'user','content':'ORIGINAL_REQUIREMENT '+('x'*5000)}]+[{'role':'user','content':'correction '+str(i)+('y'*3000)} for i in range(12)]
    out=_build_verbatim_user_section(turns)
    assert 'Every real user message' not in out
    assert 'Recover' in out and 'incomplete' in out
    assert 'hidden not owner' not in _build_verbatim_user_section([{'role':'user','content':'hidden not owner','display_kind':'internal'}])
