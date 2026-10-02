import time, os, json, multiprocessing as mp
from pathlib import Path
import pytest
from test_m18_login_round8 import mk, K, dl
from app.modules.m13_browser_agent.pc_daemon.daemon import Daemon

def _worker(args):
    tmp, key = args
    os.environ['ATLAS_PC_ANCHOR_DIR'] = str(Path(tmp)/'anchors'); os.environ['ATLAS_PC_ANCHOR_DIR2'] = str(Path(tmp)/'anchors-secondary')
    d = mk(tmp); return d._consume_submit(K(key), time.time()+100)

def test_A_full_snapshot_restore_all_three(tmp_path):
    d = mk(tmp_path); snap=Path(d.consumed_path).read_text(); a=[p.read_text() for p in d.anchor_paths()]
    assert d._consume_submit(K(1), dl()) is None
    Path(d.consumed_path).write_text(snap)
    for p,t in zip(d.anchor_paths(), a): p.write_text(t)
    print('A_full_snapshot_restore ->', mk(tmp_path)._consume_submit(K(1), dl()))

def test_B_record_lock_primary_deleted_strict(tmp_path):
    d = mk(tmp_path); armed=time.time()
    assert d._consume_submit(K(1), armed+120) is None
    Path(d.consumed_path).unlink(); Path(d.consumed_path+'.lock').unlink(); d.anchor_paths()[0].unlink()
    time.sleep(1.1)
    print('B_record_lock_anchor1_deleted ->', mk(tmp_path)._consume_submit(K(1), armed+120))

def test_C_everything_deleted(tmp_path):
    d = mk(tmp_path); armed=time.time()
    assert d._consume_submit(K(1), armed+120) is None
    for p in [Path(d.consumed_path), Path(d.consumed_path+'.lock'), *d.anchor_paths()]: p.unlink()
    print('C_everything_deleted ->', mk(tmp_path)._consume_submit(K(1), armed+120))

def test_D_old_record_old_primary_secondary_deleted(tmp_path):
    d = mk(tmp_path); snap=Path(d.consumed_path).read_text(); a=d.anchor_paths()[0].read_text()
    assert d._consume_submit(K(1), dl()) is None
    Path(d.consumed_path).write_text(snap); d.anchor_paths()[0].write_text(a); d.anchor_paths()[1].unlink()
    print('D_old_rec_old_primary_secondary_gone ->', mk(tmp_path)._consume_submit(K(1), dl()))

def test_E_multiprocess_race(tmp_path):
    with mp.Pool(8) as p: r = p.map(_worker, [(str(tmp_path), 7)]*16)
    print('E_race successes =', sum(x is None for x in r), [x for x in r if x][:2])

def test_F_record_deleted_running_then_restored_midrun(tmp_path):
    d = mk(tmp_path); assert d._consume_submit(K(1), dl()) is None
    snap = Path(d.consumed_path).read_text(); assert d._consume_submit(K(2), dl()) is None
    Path(d.consumed_path).write_text(snap)
    print('F_rollback_same_process ->', d._consume_submit(K(2), dl()))

def test_G_clock_back_token_reuse(tmp_path, monkeypatch):
    d = mk(tmp_path); t=time.time(); assert d._consume_submit(K(1), t+100) is None
    # clock jumps forward 2h (prune) then token with far deadline replay
    real=time.time; monkeypatch.setattr(time,'time',lambda: real()+7200)
    print('G_clock_forward_replay_deadline_future ->', d._consume_submit(K(1), real()+7300))

def test_H_extreme_deadline(tmp_path):
    d = mk(tmp_path)
    for dlv in (float('inf'), 1e300, float('nan')):
        try: print('H deadline', dlv, '->', d._consume_submit(K(5), dlv))
        except Exception as e: print('H deadline', dlv, 'EXC', repr(e))

def test_I_key_json_weird(tmp_path):
    d = mk(tmp_path)
    print('I', d._consume_submit(('token:a','approval:'+'x'*100000), dl()), d._consume_submit(('token:a','approval:y'), dl()))
