import copy
import json
import os
from pathlib import Path

import unittest
from agent import context_compressor as cc

if os.environ.get('HERMES_CONTEXT_SOURCE'):
    source = Path(os.environ['HERMES_CONTEXT_SOURCE'])
    exec(compile(source.read_text(), str(source), 'exec'), cc.__dict__)

CASES = [
    ('write_file', {'path':'draft.txt'}, {'status':'pending_approval'}, 'awaiting approval'),
    ('terminal', {'command':'build draft'}, {'status':'blocked','error':'policy restriction'}, 'BLOCKED'),
    ('write_file', {'path':'draft.txt'}, {'status':'blocked'}, 'BLOCKED'),
    ('terminal', {'command':'build draft'}, 'BLOCKED: user has NOT consented; do not retry', 'do not retry'),
    ('custom_tool', {}, {'status':'pending_approval'}, 'awaiting approval'),
]
def check_native_demotion_preserves_not_run(name,args,result,marker):
    content = result if isinstance(result,str) else json.dumps({**result,'detail':'x'*2000})
    if isinstance(result,str): content += ' '*2000
    rows=[{'role':'tool','tool_call_id':'call1','content':content}]
    original=copy.deepcopy(rows)
    assert cc.ContextCompressor._demote_tool_result_at(rows,0,{'call1':(name,json.dumps(args))},100)
    summary=rows[0]['content']
    assert 'not run' in summary and marker in summary
    assert 'wrote to' not in summary and '] ran ' not in summary
    assert len(summary)<cc._PRUNE_MIN_CHARS
    assert rows[0]['tool_call_id']==original[0]['tool_call_id']
    assert original[0]['content']==content

def test_success_keeps_existing_behavior():
    assert 'wrote to draft.txt' in cc._summarize_tool_result('write_file','{"path":"draft.txt"}','{"status":"success"}')

def test_embedded_blocked_document_is_not_execution_status():
    assert 'wrote to' in cc._summarize_tool_result('write_file','{"path":"draft.txt"}',json.dumps({'status':'success','content':'BLOCKED examples'}))

def test_existing_pending_round_survives_two_steers():
    rows=[{'role':'assistant','tool_calls':[{'id':'a'}]}, {'role':'tool','tool_call_id':'a','content':'unanswered'},
          {'role':'user','display_kind':cc.STEER_DISPLAY_KIND,'content':'continue'},
          {'role':'user','display_kind':cc.STEER_DISPLAY_KIND,'content':'keep source'}]
    assert list(cc._pending_tool_round(rows))==[1]

def test_malformed_scalar_remains_nonthrowing():
    for text in ['null','[1]','false','{']:
        assert isinstance(cc._summarize_tool_result('custom_tool','{}',text),str)


class NativeRefusalTests(unittest.TestCase):
    def test_demotion_cases(self):
        for case in CASES:
            with self.subTest(tool=case[0], marker=case[3]):
                check_native_demotion_preserves_not_run(*case)
    def test_success(self): test_success_keeps_existing_behavior()
    def test_embedded_document(self): test_embedded_blocked_document_is_not_execution_status()
    def test_steers(self): test_existing_pending_round_survives_two_steers()
    def test_malformed(self): test_malformed_scalar_remains_nonthrowing()

if __name__ == '__main__': unittest.main()
