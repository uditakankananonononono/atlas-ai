"""Real-model actor: a small local LLM (Qwen2.5-Instruct GGUF via
llama.cpp's llama-server) replaces the ScriptedActor.  SAME loop entry
points (run._run_baseline / run._run_verified), SAME pre-gate, SAME
floor, SAME grader, SAME MAX_STEPS / MAX_REPAIRS -- only the
decision-maker changes.

This docstring describes the MECHANISM only.  The pinned model, GGUF
sha256, runtime build, generation parameters (temperature, seed,
max_tokens), task slice and harness limits for each run live in that
run's meta.json: rev12 (0.5B validity probe, HELD_OUT[:10]) ->
rows_llm_meta.json; rev13 (1.5B, HELD_OUT[:30]) -> rows15_llm_meta.json.

Per step the model sees the task statement, a fixed tool sheet, the
accepted history with observations, and (verified loop) the latest
Violation, and must emit:
  TOOL: <name> <key=value> ...
  EXPECT: observation = <text> | <path> = <text> | none      (verified w/ contract)
The EXPECT line is the actor-stated prediction contract carried over
from the scripted worlds, COMPILED by compile_expect into Step.expect:
  'observation = V'  -> the call's observation must equal V (mirrors the
                        scripted add/concat value contracts)
  '<path> = V'       -> after-state file check (mirrors the scripted
                        write/scale after-state contracts)
  'none'             -> no contract (readback/finish in the scripted
                        actor)
All args stay STRINGS, which matches this world's schemas exactly
(paths, text, integer-text).

FORMAT FAILURES (parent addition 2, rev12 pre-registration): a
missing/invalid TOOL line or an uncompilable EXPECT never reaches the
world as a guess; the actor returns Step('__format_failure__', ...)
instead.  In the verified loop the pre-gate blocks it as unknown_tool
at zero step cost; in the baseline it executes and comes back as an
ERROR observation.  Both loops are UNCHANGED.  The harness logs the RAW
model output for EVERY step (parse failures included) and counts format
failures per task per condition, so the probe cannot silently degrade
into a formatting test.

Honest-label discipline: the actor is a real LLM, deterministic
(temperature 0, fixed seed, pinned GGUF sha256 + pinned llama.cpp
build); the world, tools, grader and held-out tasks are identical to
the registered scripted measurement.  Parser leniency (disclosed):
a bare '<tool> <args>' line naming a known tool is accepted (logged as
leniency=no_tool_prefix in the raw row).  Harness limits for CPU
feasibility (disclosed, harness-only) are pinned in the run's
meta.json."""

import json
import re
import urllib.request

from instinct_models.stepverify import Step

_SEED = 20261021
_MAX_TOKENS = 48
_TIMEOUT_S = 300
FORMAT_FAILURE_TOOL = '__format_failure__'

_TOOL_SHEET = """\
Tools (every argument is a string; integer arguments are integer text):
- list() -> the sorted list of paths, shown like ['data0.txt', 'data1.txt']
- read(path) -> the file's contents
- write(path, text) -> 'wrote N chars'
- append(path, text) -> 'appended'
- add(a, b) -> a+b as integer text
- concat(a, b, sep) -> the string a+sep+b
- scale(path, factor) -> 'scaled'
- finish(answer) -> submit the final answer and stop

Example (for a task "add the integers in x.txt and y.txt and finish"):
TOOL: read path=x.txt
EXPECT: none
then after observing the contents '5':
TOOL: read path=y.txt
EXPECT: none
then after observing '7':
TOOL: add a=5 b=7
EXPECT: observation = 12
then:
TOOL: finish answer=12
EXPECT: none"""

def compile_expect(text):
    """Compile an EXPECT line into Step.expect (obs, before, after) ->
    problem|None, or return None for 'none', or raise ValueError."""
    t = (text or '').strip()
    if t.lower() in ('', 'none', 'ok'):
        return None
    m = re.fullmatch(r'observation\s*=\s*(.+)', t)
    if not m and re.fullmatch(r'[-+\d.,a-zA-Z ]+', t) and '=' not in t:
        # leniency (disclosed): a bare value means 'observation = <value>'
        t = 'observation = ' + t
        m = re.fullmatch(r'observation\s*=\s*(.+)', t)
    if m:
        want = m.group(1).strip()

        def expect(obs, b, a, w=want):
            return None if str(obs) == w else (
                'observation was %r, I predicted %r' % (obs, w))
        return expect
    m = re.fullmatch(r'([\w./-]+)\s*=\s*(.+)', t)
    if m:
        path, want = m.group(1), m.group(2).strip()

        def expect(obs, b, a, p=path, w=want):
            got = a['files'].get(p)
            return None if got == w else (
                'after my call, %s holds %r; I stated %r' % (p, got, w))
        return expect
    raise ValueError('uncompilable EXPECT: %r' % text)


class LLMActor:
    """Callable actor with the ScriptedActor.__call__ interface:
    act(task, history, violation) -> Step | None."""

    def __init__(self, task, base_url, want_expect, model='qwen05',
                 expect_discipline=False):
        self.task = task
        self.base_url = base_url.rstrip('/')
        self.want_expect = want_expect
        # rev16 lever (i): prompt-level EXPECT:none discipline for
        # observations the model cannot predict exactly
        self.expect_discipline = expect_discipline
        self.model = model
        self.parse_failures = 0
        self.raw_log = []        # every step: {raw, parsed|parse_error}
        self._done = False

    def _prompt(self, history, violation):
        lines = [
            'You are a tool-using agent. Solve the task by calling one '
            'tool at a time.',
            '',
            'Task: ' + self.task['statement'],
            '',
            _TOOL_SHEET,
            '',
        ]
        if history:
            lines.append('Steps so far (most recent last; older '
                         'omitted):')
            for rec in history[-6:]:
                lines.append('- %s %s -> %r'
                             % (rec.step.tool, json.dumps(rec.step.args),
                                rec.observation))
            lines.append('')
        if violation is not None:
            lines.append('REJECTED by the verifier: stage=%s tool=%s: %s'
                         % (violation.stage, violation.tool,
                            violation.detail))
            lines.append('Do not repeat that call. Correct it.')
            lines.append('')
        if self.want_expect and self.expect_discipline:
            lines.append('Use EXPECT: none whenever you cannot predict the observation exactly (for example list output or file contents you have not yet read).')
        lines.append('Now reply with EXACTLY one TOOL line' + (' and one EXPECT line' if self.want_expect else '') + '. Nothing else, no explanations:')
        return '\n'.join(lines)

    def _generate(self, prompt):
        body = json.dumps({
            'model': self.model,
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': 0.0,
            'seed': _SEED,
            'max_tokens': _MAX_TOKENS,
        }).encode()
        req = urllib.request.Request(
            self.base_url + '/v1/chat/completions', data=body,
            headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:
            data = json.loads(resp.read())
        return data['choices'][0]['message']['content']

    @staticmethod
    def parse_output(text, want_expect):
        """raw text -> (tool, args, expect) or raise ValueError."""
        m = re.search(r'^\s*TOOL:\s*(\S+)([^\n]*)', text, re.M)
        if not m:
            raise ValueError('no TOOL line')
        tool = m.group(1)
        rest = (m.group(2) or '').strip()
        args = None
        if rest.startswith('{'):
            # leniency (disclosed): JSON-style args
            try:
                args = {k: str(v) for k, v in json.loads(rest).items()}
            except ValueError:
                args = None
        if args is None:
            args = {}
            for k, v in re.findall(r'(\w+)=("[^"]*"|\'[^\']*\'|[^\s]+)',
                                   rest):
                if len(v) >= 2 and v[0] == v[-1] and v[0] in '"\'':
                    v = v[1:-1]
                args[k] = v                     # strings: matches schemas
        expect = None
        if want_expect:
            me = re.search(r'^\s*EXPECT:\s*(.+)$', text, re.M)
            if not me:
                raise ValueError('no EXPECT line')
            etext = me.group(1).strip()
            if len(etext) >= 2 and etext[0] == etext[-1] and etext[0] in '"\'':
                etext = etext[1:-1]      # leniency (disclosed): quoted EXPECT
            expect = compile_expect(etext)          # ValueError if bad
        return tool, args, expect

    def __call__(self, task, history, violation):
        if self._done:
            return None
        if history and history[-1].step.tool == 'finish' and not str(
                history[-1].observation).startswith('ERROR:'):
            self._done = True
            return None
        raw = self._generate(self._prompt(history, violation))
        try:
            tool, args, expect = self.parse_output(raw, self.want_expect)
            self.raw_log.append({'raw': raw, 'tool': tool, 'args': args})
            return Step(tool, args, expect=expect)
        except ValueError as e:
            self.parse_failures += 1
            self.raw_log.append({'raw': raw, 'parse_error': str(e)})
            return Step(FORMAT_FAILURE_TOOL, {}, note=raw[:160])
