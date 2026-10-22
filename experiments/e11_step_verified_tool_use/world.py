"""E11 virtual workspace world and its tool contracts.

The world is a dict {'files': {path: text}}.  Every file used by a
task holds a signed integer as text.  Tools: list, read, write,
append, add, finish.  This module also defines the ToolSpec registry
the step verifier checks against.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                '..', '..', '..', 'backend'))
from instinct_models.stepverify import ToolSpec  # noqa: E402


class WorldError(Exception):
    """A visible execution error (returned to a ReAct-style actor as
    the observation text)."""


# rev8: FLAKY EXECUTION channel.  When EXEC_FAULT_P > 0 the WORLD
# silently mis-executes a write/append with that probability (the
# stored text loses its last character).  This is an execution fault,
# not an intent fault: the args are exactly what the actor meant, so
# argument-schema validation and preconditions are blind to it - only
# post-execution effect checking (the spec floor OR the actor's
# stated prediction) can catch it.  Seeded per (task, seed) via
# seed_faults so conditions stay paired.
import random as _random

EXEC_FAULT_P = 0.0
_fault_rng = _random.Random('e11-flaky-unset')


def seed_faults(key):
    global _fault_rng
    _fault_rng = _random.Random('e11-flaky-%s' % key)


def _maybe_fault(text):
    if EXEC_FAULT_P > 0.0 and text and _fault_rng.random() < EXEC_FAULT_P:
        return text[:-1]
    return text


def execute(state, tool, args):
    """(state, tool, args) -> (observation, new_state). Raises
    WorldError on invalid execution (missing file, bad number)."""
    files = state['files']
    if tool == 'list':
        return sorted(files), state
    if tool == 'read':
        if args['path'] not in files:
            raise WorldError('no such file: %s' % args['path'])
        return files[args['path']], state
    if tool == 'write':
        new = dict(files)
        new[args['path']] = _maybe_fault(args['text'])
        return 'wrote %d chars' % len(args['text']), {'files': new}
    if tool == 'append':
        if args['path'] not in files:
            raise WorldError('no such file: %s' % args['path'])
        new = dict(files)
        new[args['path']] = _maybe_fault(files[args['path']]
                                         + args['text'])
        return 'appended', {'files': new}
    if tool == 'add':
        try:
            total = int(args['a']) + int(args['b'])
        except ValueError:
            raise WorldError('add needs integer text, got %r and %r'
                             % (args['a'], args['b']))
        return str(total), state
    if tool == 'concat':
        return args['a'] + args['sep'] + args['b'], state
    if tool == 'scale':
        # rev4 mutating world: an INVALID scale corrupts the target
        # before reporting the error - the side effect cannot be
        # un-happened by observing the failure (this is the case the
        # pre-gate exists for)
        if args['path'] not in files:
            raise WorldError('no such file: %s' % args['path'])
        new = dict(files)
        try:
            factor = int(args['factor'])
            new[args['path']] = str(int(files[args['path']]) * factor)
            return 'scaled', {'files': new}
        except ValueError:
            new[args['path']] = 'CORRUPT'
            return 'ERROR: factor must be integer text, got %r' % (
                args['factor'],), {'files': new}
    if tool == 'finish':
        return args.get('answer', ''), state
    raise WorldError('no such tool: %s' % tool)


def _exists(state, args):
    if args['path'] not in state['files']:
        return 'no such file: %s' % args['path']
    return None


def _int_text(args_key):
    def pre(state, args):
        try:
            int(args[args_key])
        except (ValueError, TypeError):
            return '%s must be integer text, got %r' % (
                args_key, args.get(args_key))
        return None
    return pre


def _write_effect(before, args):
    def pred(obs, s_before, s_after):
        got = s_after['files'].get(args['path'])
        if got != args['text']:
            return 'file %s holds %r, not the written %r' % (
                args['path'], got, args['text'])
        return None
    return pred


def _append_effect(before, args):
    def pred(obs, s_before, s_after):
        want = s_before['files'][args['path']] + args['text']
        got = s_after['files'].get(args['path'])
        if got != want:
            return 'file %s holds %r, want %r' % (args['path'], got, want)
        return None
    return pred


def _read_effect(before, args):
    def pred(obs, s_before, s_after):
        if obs != s_before['files'][args['path']]:
            return 'read returned %r, file holds %r' % (
                obs, s_before['files'][args['path']])
        return None
    return pred


def _add_effect(before, args):
    def pred(obs, s_before, s_after):
        want = str(int(args['a']) + int(args['b']))
        if obs != want:
            return 'add returned %r, want %r' % (obs, want)
        return None
    return pred


def _concat_effect(before, args):
    def pred(obs, s_before, s_after):
        want = args['a'] + args['sep'] + args['b']
        if obs != want:
            return 'concat returned %r, want %r' % (obs, want)
        return None
    return pred


def _scale_effect(before, args):
    def pred(obs, s_before, s_after):
        try:
            want = str(int(s_before['files'][args['path']])
                       * int(args['factor']))
        except ValueError:
            return None     # the precondition owns malformed factors
        got = s_after['files'].get(args['path'])
        if got != want:
            return 'file %s holds %r, want %r' % (
                args['path'], got, want)
        return None
    return pred


def _scale_pre(state, args):
    if args['path'] not in state['files']:
        return 'no such file: %s' % args['path']
    try:
        int(args['factor'])
    except (ValueError, TypeError):
        return 'factor must be integer text, got %r' % (
            args.get('factor'),)
    return None


TOOLS = [
    ToolSpec('list'),
    ToolSpec('read', required=('path',), arg_types={'path': str},
             pre=_exists, effect=_read_effect),
    ToolSpec('write', required=('path', 'text'),
             arg_types={'path': str, 'text': str}, effect=_write_effect),
    ToolSpec('append', required=('path', 'text'),
             arg_types={'path': str, 'text': str},
             pre=_exists, effect=_append_effect),
    ToolSpec('add', required=('a', 'b'),
             arg_types={'a': str, 'b': str},
             pre=lambda st, ar: (_int_text('a')(st, ar)
                                 or _int_text('b')(st, ar)),
             effect=_add_effect),
    ToolSpec('concat', required=('a', 'b', 'sep'),
             arg_types={'a': str, 'b': str, 'sep': str},
             effect=_concat_effect),
    ToolSpec('scale', required=('path', 'factor'),
             arg_types={'path': str, 'factor': str},
             pre=_scale_pre, effect=_scale_effect),
    ToolSpec('finish', required=('answer',), arg_types={'answer': str}),
]
