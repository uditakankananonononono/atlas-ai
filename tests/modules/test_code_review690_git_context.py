import subprocess
from app.modules.m20_general_cognitive_worker.code_review690 import parse_unified_diff,review


def test_real_git_diff_with_context_line_positions(tmp_path):
    def git(*args):return subprocess.check_output(['git','-C',str(tmp_path),*args]).decode()
    git('init');git('config','user.email','fixture@example.test');git('config','user.name','Fixture')
    path=tmp_path/'sample.py';path.write_text('first = 1\nsecond = 2\nthird = 3\nfourth = 4\n')
    git('add','sample.py');git('commit','-m','initial')
    path.write_text('first = 1\nsecond = 2\nprint("debug")\nthird = 3\nfourth = 4\n')
    diff=git('diff','--no-ext-diff','--no-textconv')
    parsed=parse_unified_diff(diff)
    assert parsed==[{'path':'sample.py','added':[(3,'print("debug")')],'removed':0}]
    result=review(diff,['debug'],author='fixture')
    assert result['added_lines']==1
    finding=next(x for x in result['findings'] if x['rule']=='debug-leftover')
    assert finding['line']==3 and finding['path']=='sample.py'


def test_context_replacement_and_multiple_hunks():
    diff='--- a/x.py\n+++ b/x.py\n@@ -1,3 +1,3 @@\n keep\n-old\n+new\n tail\n@@ -10,2 +10,3 @@\n keep\n+extra\n end\n'
    parsed=parse_unified_diff(diff)
    assert parsed[0]['added']==[(2,'new'),(11,'extra')] and parsed[0]['removed']==1
