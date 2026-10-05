"""Execute source update paths only in bounded disposable repositories."""
import contextlib
import hashlib
import io
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from hermes_cli import main as cli, update_cmd, update_receipt
from tests.hermes_cli.test_update_target_identity import update_tree, git

@pytest.mark.parametrize('overlap',[False,True])
def test_actual_hermes_update_preserves_installed_compressor(update_tree,monkeypatch,overlap):
    t=update_tree
    monkeypatch.setenv("HERMES_GATEWAY_LOCK_DIR", str(t.clone.parent / "host-state"))
    monkeypatch.setattr("hermes_cli.update_owning_install.retarget_to_owning_install", lambda *_: None)
    source='agent/context_compressor.py'
    base=b'def summary():\n    return "pending tool"\n'
    live=b'def summary():\n    return "refused tool; no execution"\n'
    for root in [t.origin,t.clone]:
        (root/'agent').mkdir(exist_ok=True)
    (t.origin/source).write_bytes(base)
    (t.origin/'native.txt').write_text('native base\n')
    git(t.origin,'add',source,'native.txt');git(t.origin,'commit','-qm','fixture compressor base')
    git(t.clone,'fetch','origin');git(t.clone,'checkout','--detach','origin/main')
    before=git(t.clone,'rev-parse','HEAD')
    # An actual source update: conflicting upstream line or unrelated source.
    if overlap:
        changed=live.splitlines()
        baseline=base.splitlines()
        import difflib
        matcher=difflib.SequenceMatcher(None,baseline,changed,autojunk=False)
        block=next(x for x in matcher.get_opcodes() if x[0]=='replace')
        i=block[1]; baseline[i:i+1]=[b'# upstream changed the same repaired line']
        (t.origin/source).write_bytes(b'\n'.join(baseline)+b'\n')
    else:
        (t.origin/'upstream.txt').write_text('new upstream capability\n')
    git(t.origin,'add',source if overlap else 'upstream.txt');git(t.origin,'commit','-qm','next update')
    target=git(t.origin,'rev-parse','HEAD')
    (t.clone/source).write_bytes(live)
    (t.clone/'native.txt').write_text('unrelated native edit\n')
    git(t.clone,'add','native.txt')
    (t.clone/'untracked.txt').write_text('retain untracked native data\n')
    original_index = (t.clone/'.git/index').read_bytes()
    original_stashes = git(t.clone,'stash','list')
    monkeypatch.setattr(update_cmd,'_UPDATE_CRITICAL_MODULES',())
    monkeypatch.setattr(cli,'_sync_with_upstream_if_needed',lambda *a,**k:False)
    # Bypass release lookup only: consume the exact local upstream commit.
    t.args.channel='main';t.args.branch='main'
    try:
        cli.cmd_update(t.args)
    except SystemExit as exc:
        assert overlap and exc.code!=0
    assert (t.clone/source).read_bytes()==live, 'update displaced the installed compressor repair'
    assert (t.clone/'native.txt').read_text()=='unrelated native edit\n'
    assert (t.clone/'untracked.txt').read_text()=='retain untracked native data\n'
    if overlap:
        assert git(t.clone,'rev-parse','HEAD')==before
        assert (t.clone/'.git/index').read_bytes()==original_index
        assert git(t.clone,'stash','list')==original_stashes
        assert t.requests==[]
    else:
        assert git(t.clone,'rev-parse','HEAD')==target

@pytest.mark.parametrize('case',['untracked_collision','missing_target','unrelated'])
def test_candidate_preflight_reports_exact_overlap_without_mutation(tmp_path,case,capsys):
    git(tmp_path,'init','-q','-b','main')
    git(tmp_path,'config','user.name','Fixture');git(tmp_path,'config','user.email','fixture@invalid')
    (tmp_path/'base.txt').write_text('base\n');git(tmp_path,'add','base.txt');git(tmp_path,'commit','-qm','base')
    before=git(tmp_path,'rev-parse','HEAD')
    (tmp_path/'native file.txt').write_text('upstream version\n');git(tmp_path,'add','native file.txt');git(tmp_path,'commit','-qm','target')
    target=git(tmp_path,'rev-parse','HEAD');git(tmp_path,'checkout','--detach',before)
    path='native file.txt' if case=='untracked_collision' else 'different.txt'
    (tmp_path/path).write_text('native preserved\n')
    index=(tmp_path/'.git/index').read_bytes()
    if case=='unrelated':
        update_cmd._refuse_overlapping_local_update(['git'],tmp_path,target)
    else:
        with pytest.raises(SystemExit):
            update_cmd._refuse_overlapping_local_update(['git'],tmp_path,'missing-target' if case=='missing_target' else target)
        output=capsys.readouterr().out
        assert ('native file.txt' if case=='untracked_collision' else 'Cannot verify') in output
    assert (tmp_path/path).read_text()=='native preserved\n'
    assert (tmp_path/'.git/index').read_bytes()==index
    assert git(tmp_path,'rev-parse','HEAD')==before


"""Regression from independent review: retain index and worktree independently."""
@pytest.mark.parametrize('case', ['cancelled','deletion','rename_from','rename_to'])
@pytest.mark.parametrize('overlap', [True, False])
def test_update_preserves_index_and_worktree(update_tree, monkeypatch, case, overlap):
    t=update_tree
    monkeypatch.setenv('HERMES_GATEWAY_LOCK_DIR', str(t.clone.parent/'host-state'))
    monkeypatch.setattr('hermes_cli.update_owning_install.retarget_to_owning_install',lambda *_:None)
    for name in ('owned.py','unrelated.py'):
        (t.origin/name).write_text('base\n')
    git(t.origin,'add','owned.py','unrelated.py');git(t.origin,'commit','-qm','base owned')
    git(t.clone,'fetch','origin');git(t.clone,'checkout','--detach','origin/main')
    head=git(t.clone,'rev-parse','HEAD')
    incoming=('renamed.py' if case=='rename_to' else 'owned.py') if overlap else 'unrelated.py'
    (t.origin/incoming).write_text('upstream\n');git(t.origin,'add',incoming);git(t.origin,'commit','-qm','incoming')
    target=git(t.origin,'rev-parse','HEAD')
    if case=='cancelled':
        (t.clone/'owned.py').write_text('# owner staged repair\n');git(t.clone,'add','owned.py');(t.clone/'owned.py').write_text('base\n')
        assert git(t.clone,'diff','HEAD','--name-only')==''
    elif case=='deletion':
        git(t.clone,'rm','owned.py');(t.clone/'owned.py').write_text('base\n')
    else:
        git(t.clone,'mv','owned.py','renamed.py');(t.clone/'renamed.py').write_text('# unstaged after rename\n')
    paths=('owned.py','renamed.py')
    def state():
        return {p:((t.clone/p).read_bytes() if (t.clone/p).exists() else None) for p in paths}
    before=state(); index=(t.clone/'.git/index').read_bytes()
    entries=git(t.clone,'ls-files','--stage','--',*paths)
    stashes=git(t.clone,'stash','list')
    monkeypatch.setattr(update_cmd,'_UPDATE_CRITICAL_MODULES',())
    monkeypatch.setattr(cli,'_sync_with_upstream_if_needed',lambda *a,**k:False)
    t.args.channel='main';t.args.branch='main'
    code=0
    try: cli.cmd_update(t.args)
    except SystemExit as e: code=e.code
    assert state()==before
    assert git(t.clone,'ls-files','--stage','--',*paths)==entries, 'staged owner state lost'
    assert git(t.clone,'stash','list')==stashes
    if overlap:
        assert code!=0
        assert git(t.clone,'rev-parse','HEAD')==head
        assert (t.clone/'.git/index').read_bytes()==index
    else:
        assert code==0
        assert git(t.clone,'rev-parse','HEAD')==target
