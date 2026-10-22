"""Tests for p235 concepts batch 1177: RFC 7396 JSON Merge Patch over decoded caller-supplied values. Pure functions over caller data; claims asserted False."""
import ast
import builtins
import copy
import importlib.util
import inspect
import os
import re
import signal
import subprocess
import sys
import tracemalloc
import traceback
import types
import unicodedata

import pytest
import random
from importlib.util import find_spec

REG = 'app.modules.instinct_doc.p235_concepts_registry'
MODNAME = 'app.modules.instinct_doc.p235_concepts_batch1177_jsonmerge'
NAMES = ('value_reason', 'type_name', 'canonical', 'merge_equal', 'merge_patch',
         'merge_patch_list', 'merge_ops', 'removed_paths', 'diff', 'get_path')
PRIVATE = ('_scan', '_check', '_copy', '_canon', '_eq', '_merge', '_ops', '_removals', '_diff')
DOC_EXACT = 'p235 concepts batch 1177 (rev 0): RFC 7396 JSON Merge Patch processing over decoded caller-supplied values. Pure functions over caller-supplied data. No retrieval, no network, no clock. This unit never parses or serializes JSON text: inputs are decoded Python values only. Every claim in CLAIMS is asserted False: this module is not the standard, not an authority, not certified, not current, not complete; it performs no HTTP PATCH negotiation, registers no media type and makes no authorization decision. ADJACENT names the neighbouring units this unit deliberately does not implement: the RFC 8259 sections 2-7 JSON text grammar (b1214), the RFC 7464 JSON text sequence framing (b1176), and RFC 6902 JSON Patch with RFC 6901 JSON Pointer (b1178).\n\nLIVE-READ SOURCES (read live, quoted verbatim below and mechanically matched against the whitespace-collapsed RFC text with the page headers and footers removed):\n- RFC 7396, JSON Merge Patch, Standards Track, October 2014, Hoffman & Snell. rfc7396.txt is 12791 bytes, sha256 545e1d61667c243ea14d6b1a56212370a26d46e1acd441803805fcdecd9164c6.\n- RFC 8259, The JavaScript Object Notation (JSON) Data Interchange Format, Standards Track, December 2017, for the value data model the decoded values follow. rfc8259.txt is 28360 bytes, sha256 61a5378f4255c720beb2a4b4a63b29540147c140f36988bf086291989b4cd2d7.\n- RFC 7159, March 2014, because 7396\'s own normative reference is 7159 (section 6.1). rfc7159.txt is 27451 bytes, sha256 50aa72534210945457f5460a50f263c1d6cf87a3da8c814c1d9f54cb04f22342. The rfc-editor info page for RFC 7159 shows Obsoleted by RFC 8259; the value definition cited here is the same text in both documents.\n- The rfc-editor info page for RFC 7396 lists Obsoletes (1): RFC 7386, and shows no Obsoleted by entry and no Updated by entry: RFC 7396 is the current JSON Merge Patch document. The info page for RFC 8259 likewise shows no Obsoleted by entry. CLAIMS current is still False.\n- errata.json (sha256 2771053324fcbbc3f775f4b6d7514c204ba1a4c65077c4fa866614d392640c66) records 0 errata for RFC 7396. It records 16 errata for RFC 8259: 5218 (Rejected, Technical, section 12), 5853 (Rejected, Technical, section 11), 7600 (Verified, Technical, section 6), 7603 (Verified, Technical, section 1), 7617 (Rejected, Technical, section 6), 6208 (Rejected, Technical, section 8.1), 7307 (Rejected, Technical, section 3), 7383 (Verified, Technical, section 3), 8874 (Rejected, Technical, section 6), 7650 (Held for Document Update, Technical, section 7), 8438 (Held for Document Update, Editorial, section 14.1), 7673 (Rejected, Technical, section 7), 5210 (Verified, Editorial, GLOBAL), 8622 (Rejected, Technical, section 4), 5318 (Verified, Editorial, section 7) and 9095 (Reported, Technical, section 11). Two touch the section 3 value definition cited here, and their pages were read directly: 7383 (Verified, Technical, section 3) corrects the capitalization of hex literals in the false/null ABNF, a text-grammar detail that changes no decoded value, and 7307 (Rejected, Technical, section 3) was rejected, the verifier noting the original specification is clear. RFC 7159 carries 9 errata in the same index: 3915 (Verified, Technical, section 12), 3984 (Rejected, Technical, section 7), 3983 (Rejected, Technical, section 2), 4220 (Rejected, Technical, section 7), 4264 (Verified, Editorial, section 15.2), 4298 (Rejected, Technical, section 7), 4336 (Verified, Editorial, Appendix A), 4388 (Held for Document Update, Editorial, section 1.2) and 8437 (Rejected, Technical, section 4); none touches the section 3 value definition used here. RFC 7386, the obsoleted predecessor, carries 1 erratum: 4132 (Verified, Technical, section 2). The counts are taken from that single JSON index and are not independently confirmed against the per-erratum pages. OURS: no erratum is applied. The RFC texts decide.\n\nSOURCED (the RFC text):\n- The algorithm (7396 section 2): "define MergePatch(Target, Patch): if Patch is an Object: if Target is not an Object: Target = {} # Ignore the contents and set it to an empty Object for each Name/Value pair in Patch: if Value is null: if Name exists in Target: remove the Name/Value pair from Target else: Target[Name] = MergePatch(Target[Name], Value) return Target else: return Patch"\n- Arguments (section 2): "The Target argument can be any JSON value or undefined. The Patch argument can be any JSON value."\n- Whole replacement (section 2): "If the patch is anything other than an object, the result will always be to replace the entire target with the entire patch."\n- No partial patch of a non-object (section 2): "Also, it is not possible to patch part of a target that is not an object, such as to replace just some of the values in an array."\n- Data items, not text (section 2): "The MergePatch operation is defined to operate at the level of data items, not at the level of textual representation." "There is no expectation that the MergePatch operation will preserve features at the textual-representation level such as white space, member ordering, number precision beyond what is available in the target\'s implementation, and so forth."\n- Duplicate names (section 2): "In addition, even if the target implementation allows multiple name/value pairs with the same name, the result of the MergePatch operation on such objects is not defined."\n- Null removes (section 1): "Null values in the merge patch are given special meaning to indicate the removal of existing values in the target."\n- Fit (section 1): "This design means that merge patch documents are suitable for describing modifications to JSON documents that primarily use objects for their structure and do not make use of explicit null values. The merge patch format is not appropriate for all JSON syntaxes."\n- Media type (section 4): "Subtype name: merge-patch+json"\n- Normative reference (section 6.1): "Bray, T., "The JavaScript Object Notation (JSON) Data Interchange Format", RFC 7159, March 2014,"\n- The value model (RFC 8259 section 3): "A JSON value MUST be an object, array, number, or string, or one of the following three literal names: false null true" "value = false / null / true / object / array / number / string"\n- Objects (8259 section 4): "An object structure is represented as a pair of curly brackets surrounding zero or more name/value pairs (or members). A name is a string." "The names within an object SHOULD be unique."\n- Arrays (8259 section 5): "An array structure is represented as square brackets surrounding zero or more values (or elements). Elements are separated by commas." "There is no requirement that the values in an array be of the same type."\n- Numbers (8259 section 6): "Numeric values that cannot be represented in the grammar below (such as Infinity and NaN) are not permitted."\n\nOURS (conventions this module adds, each pinned by tests):\n1. Decoded values only. Inputs are Python values, never JSON text; parsing and serializing text belongs to the adjacent grammar units. The mapping uses exact built-in types by identity: dict is object, list is array, str is string, int and float are number, bool is the true and false literals, None is null. Subclasses of any of these are refused as type. A hostile __eq__, __hash__ or metaclass is never consulted: validation uses type identity and membership only.\n2. Numbers. int of any size and finite float are numbers. NaN and the two infinities are refused (float.nan, float.inf): 8259 section 6 does not permit them.\n3. No mutation, fresh results. merge_patch, merge_patch_list, canonical and diff return freshly built dict and list structures, and the set values inside merge_ops are fresh; inputs are never mutated and results share no mutable structure with any input. get_path is the exception: it returns the found value itself, not a copy.\n4. Member order. Patch members are visited in dict insertion order, matching "for each Name/Value pair in Patch"; merge_ops, removed_paths and the diff member order follow the same rule. merge_equal ignores member order, since an object is an unordered collection of name/value pairs (8259 section 4). canonical sorts members by Unicode code point (plain str order).\n5. Numeric equality. merge_equal compares int and float by value, so 1 equals 1.0 and -0.0 equals 0.0; a bool is never equal to a number: True does not equal 1; likewise False does not equal 0. Every other type pair compares strictly.\n6. Patch nulls remove, target nulls are data. A null member in the patch removes the target member when it exists and is a no-op otherwise; null values already in the target survive untouched, as in the Appendix A case {"e":null} patched by {"a":1} giving {"e":null,"a":1}.\n7. Absent members and nested nulls. MergePatch(Target[Name], Value) with Name absent is MergePatch(undefined, Value), and undefined is not an object, so a fresh empty object is used; a null member inside an added object subtree therefore vanishes, exactly as the last Appendix A case shows: {} patched by {"a":{"bb":{"ccc":null}}} gives {"a":{"bb":{}}}. This module passes None for absent members; null and undefined behave identically under the pseudocode\'s "is not an Object" test.\n8. diff (no RFC basis; the RFC defines only application). diff(original, modified) returns {} when original and modified are equal objects; equal non-object values yield a deep copy of modified instead, because any object patch, even an empty one, discards a non-object target and rebuilds it as an object (section 2). When both are objects and differ, it emits, in modified member order, a deep copy of each added member value and a recursive diff of each changed member, then, in original member order, None for each removed member; otherwise a deep copy of modified. The known limit, pinned by tests: an object member whose modified value is null cannot be expressed (null removes), and a null member inside an added object subtree vanishes on application (OURS 7), so merge_patch(original, diff(original, modified)) reproduces modified exactly unless such null members exist, and then differs only at them.\n9. merge_ops op shapes: (\'set\', path, value) and (\'remove\', path), with path a tuple of member names from the root and () naming the whole value. A non-object patch is the single op (\'set\', (), copy-of-patch). When the patch member is an object and the target member is an object, the list recurses; every other changed member is one set op whose value is the result the pseudocode would assign there, so an added object already has its null members removed (OURS 7).\n10. get_path addressing (no RFC basis): the path is a tuple of exact str steps (object members) or exact int steps (array indices). bool steps are step.type, never indices. Negative indices are path.missing, not Python-style wraparound.\n\nCAPS AND CLOSURE: DEPTH_CAP is 32 container nestings and NODE_CAP is 4096 counted values for every value input; every value, container or scalar, counts once, and object names are not counted. merge_patch_list refuses more than NODE_CAP patches and get_path refuses a path longer than NODE_CAP steps; both lengths are checked before any content is read. Every result is built from nodes of the inputs and is never larger than the inputs that built it: merge_patch and merge_patch_list results are bounded by the target plus the patches, diff by the original plus the modified, and canonical, removed_paths and the merge_ops op values by their own input.\n\nFUNCTIONS, in this order: value_reason, type_name, canonical, merge_equal, merge_patch, merge_patch_list, merge_ops, removed_paths, diff, get_path. Errors are ValueError with the text P235:<function>:<code>. A code is bad_type:<name> (exact built-in type by identity; subclasses and bool-for-int refused) for the non-value arguments, bad_value:<name>.length, or bad_value:<name>.<reason>.\n\nREASONS, in check order (the first failure decides):\n- value_reason: never raises; it classifies any object. \'ok\' or the first fault of a single preorder traversal (an object\'s names are checked first, in insertion order, then its children in insertion order; array items in index order): depth (a container nested deeper than DEPTH_CAP), then nodes (the running count crossing NODE_CAP at that value), then type (not an exact dict, list, str, int, float, bool or None), then key (an object name that is not an exact str), then float.nan, then float.inf.\n- type_name and canonical: bad_value:value.<the value_reason fault>.\n- merge_equal: bad_value:a.<fault>, then bad_value:b.<fault>.\n- merge_patch and merge_ops: bad_value:target.<fault>, then bad_value:patch.<fault>.\n- merge_patch_list: bad_value:target.<fault>, then bad_type:patches, bad_value:patches.length, then bad_value:patches.item.<fault> for the first faulty patch in list order.\n- removed_paths: bad_value:patch.<fault>.\n- diff: bad_value:original.<fault>, then bad_value:modified.<fault>.\n- get_path: bad_value:value.<fault>, then bad_type:path, bad_value:path.length, then per step in path order bad_value:path.step.type (a step that is not an exact str or exact int; bool is refused here), then while walking: step.kind (an int step at an object or a str step at an array), path.missing (an absent name or an index outside 0..len-1; negative indices are missing), path.leaf (a step remains at a scalar).\n\nOUTPUT ORDER: type_name returns the 8259 section 3 name: \'object\', \'array\', \'string\', \'number\', \'true\', \'false\' or \'null\'. canonical returns the value with every object\'s members sorted by Unicode code point, recursively; array order is kept. merge_patch and merge_patch_list return the merged value: surviving target members keep their position, and members added by the patch are appended in patch visit order. merge_ops returns a tuple of ops in the pseudocode\'s visit order. removed_paths returns a tuple of name-path tuples in preorder, insertion order. diff returns a patch value whose members are ordered as OURS 8 states. get_path returns the found value itself, not a copy.\n'
QUOTES = ['define MergePatch(Target, Patch): if Patch is an Object: if Target is not an Object: Target = {} # Ignore the contents and set it to an empty Object for each Name/Value pair in Patch: if Value is null: if Name exists in Target: remove the Name/Value pair from Target else: Target[Name] = MergePatch(Target[Name], Value) return Target else: return Patch', 'The Target argument can be any JSON value or undefined. The Patch argument can be any JSON value.', 'If the patch is anything other than an object, the result will always be to replace the entire target with the entire patch.', 'Also, it is not possible to patch part of a target that is not an object, such as to replace just some of the values in an array.', 'The MergePatch operation is defined to operate at the level of data items, not at the level of textual representation.', "There is no expectation that the MergePatch operation will preserve features at the textual-representation level such as white space, member ordering, number precision beyond what is available in the target's implementation, and so forth.", 'In addition, even if the target implementation allows multiple name/value pairs with the same name, the result of the MergePatch operation on such objects is not defined.', 'Null values in the merge patch are given special meaning to indicate the removal of existing values in the target.', 'This design means that merge patch documents are suitable for describing modifications to JSON documents that primarily use objects for their structure and do not make use of explicit null values. The merge patch format is not appropriate for all JSON syntaxes.', 'Subtype name: merge-patch+json', 'Bray, T., "The JavaScript Object Notation (JSON) Data Interchange Format", RFC 7159, March 2014,', 'A JSON value MUST be an object, array, number, or string, or one of the following three literal names: false null true', 'value = false / null / true / object / array / number / string', 'An object structure is represented as a pair of curly brackets surrounding zero or more name/value pairs (or members). A name is a string.', 'The names within an object SHOULD be unique.', 'An array structure is represented as square brackets surrounding zero or more values (or elements). Elements are separated by commas.', 'There is no requirement that the values in an array be of the same type.', 'Numeric values that cannot be represented in the grammar below (such as Infinity and NaN) are not permitted.']
HERE = os.path.dirname(os.path.abspath(__file__))
import app.modules.instinct_doc.p235_concepts_batch1177_jsonmerge as m  # noqa: E402
MODPATH = m.__file__


def _prefix():
    spec = importlib.util.spec_from_file_location('b1177_pfx', MODPATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:
        mod.make_fail('x')('c')
    except ValueError as e:
        return str(e)[:-len('x:c')]


PFX = _prefix()


class _Alarm(AssertionError):
    pass


@pytest.fixture(autouse=True)
def _alarm():
    def handler(signum, frame):
        raise _Alarm('ALARM2S test exceeded 2 seconds')
    old = signal.signal(signal.SIGALRM, handler)
    signal.setitimer(signal.ITIMER_REAL, 2.0)
    yield
    signal.setitimer(signal.ITIMER_REAL, 0)
    signal.signal(signal.SIGALRM, old)


@pytest.fixture
def mp(monkeypatch):
    return monkeypatch


def fresh(name='b1177_fresh'):
    spec = importlib.util.spec_from_file_location(name, MODPATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.modules.pop(name, None)
    return mod


def E(fn, code):
    return ('err', PFX + fn + ':' + code)


def run(fn, *args, mod=None):
    try:
        return ('ok', getattr(mod or m, fn)(*args))
    except ValueError as e:
        return ('err', str(e))


# ---- independent oracle: direct recursive transcriptions of the section 2 pseudocode and the OURS conventions ----
def o_check(v, d=None, ctr=None):
    if ctr is None:
        ctr = [0]
    if d is None:
        t0 = type(v)
        d = 1 if t0 is dict or t0 is list else 0
    t = type(v)
    if (t is dict or t is list) and d > 32:
        return 'depth'
    ctr[0] += 1
    if ctr[0] > 4096:
        return 'nodes'
    if t is dict:
        for k in v:
            if type(k) is not str:
                return 'key'
        for k in v:
            kv = v[k]
            tk = type(kv)
            r = o_check(kv, d + 1 if tk is dict or tk is list else d, ctr)
            if r != 'ok':
                return r
        return 'ok'
    if t is list:
        for x in v:
            tx = type(x)
            r = o_check(x, d + 1 if tx is dict or tx is list else d, ctr)
            if r != 'ok':
                return r
        return 'ok'
    if t is str or t is bool or t is int or v is None:
        return 'ok'
    if t is float:
        if v != v:
            return 'float.nan'
        if v == float('inf') or v == -float('inf'):
            return 'float.inf'
        return 'ok'
    return 'type'


def o_merge(t, p):
    if type(p) is dict:
        base = copy.deepcopy(t) if type(t) is dict else {}
        for k in p:
            v = p[k]
            if v is None:
                if k in base:
                    del base[k]
            else:
                base[k] = o_merge(base[k] if k in base else None, v)
        return base
    return copy.deepcopy(p)


def o_eq(a, b):
    ta = type(a)
    tb = type(b)
    if ta is bool or tb is bool:
        return ta is tb and a == b
    if (ta is int or ta is float) and (tb is int or tb is float):
        return a == b
    if ta is not tb:
        return False
    if ta is dict:
        if len(a) != len(b):
            return False
        for k in a:
            if k not in b or not o_eq(a[k], b[k]):
                return False
        return True
    if ta is list:
        return len(a) == len(b) and all(o_eq(a[i], b[i]) for i in range(len(a)))
    return a == b


def o_apply_ops(t, p, ops):
    # apply ('set', path, value) / ('remove', path) ops to a deep copy; when
    # the target is not an object and the patch is, the target is discarded.
    base = copy.deepcopy(t) if type(t) is dict or type(p) is not dict else {}
    for op in ops:
        kind = op[0]
        path = op[1]
        if path == ():
            base = copy.deepcopy(op[2]) if kind == 'set' else None
            continue
        cur = base
        for step in path[:-1]:
            if type(cur) is not dict or step not in cur:
                cur = None
                break
            cur = cur[step]
        if type(cur) is not dict:
            continue
        if kind == 'set':
            cur[path[-1]] = copy.deepcopy(op[2])
        elif path[-1] in cur:
            del cur[path[-1]]
    return base


def o_remove_hits(t, p, path=()):
    out = []
    if type(p) is dict:
        base = t if type(t) is dict else {}
        for k in p:
            v = p[k]
            if v is None:
                if k in base:
                    out.append(path + (k,))
            elif type(v) is dict and k in base and type(base[k]) is dict:
                out += o_remove_hits(base[k], v, path + (k,))
    return out


APPENDIX_A = [
    ({'a': 'b'}, {'a': 'c'}, {'a': 'c'}),
    ({'a': 'b'}, {'b': 'c'}, {'a': 'b', 'b': 'c'}),
    ({'a': 'b'}, {'a': None}, {}),
    ({'a': 'b', 'b': 'c'}, {'a': None}, {'b': 'c'}),
    ({'a': ['b']}, {'a': 'c'}, {'a': 'c'}),
    ({'a': 'c'}, {'a': ['b']}, {'a': ['b']}),
    ({'a': {'b': 'c'}}, {'a': {'b': 'd', 'c': None}}, {'a': {'b': 'd'}}),
    ({'a': [{'b': 'c'}]}, {'a': [1]}, {'a': [1]}),
    (['a', 'b'], ['c', 'd'], ['c', 'd']),
    ({'a': 'b'}, ['c'], ['c']),
    ({'a': 'foo'}, None, None),
    ({'a': 'foo'}, 'bar', 'bar'),
    ({'e': None}, {'a': 1}, {'e': None, 'a': 1}),
    ([1, 2], {'a': 'b', 'c': None}, {'a': 'b'}),
    ({}, {'a': {'bb': {'ccc': None}}}, {'a': {'bb': {}}}),
]
EX3_TARGET = {'title': 'Goodbye!', 'author': {'givenName': 'John', 'familyName': 'Doe'},
              'tags': ['example', 'sample'], 'content': 'This will be unchanged'}
EX3_PATCH = {'title': 'Hello!', 'phoneNumber': '+01-123-456-7890', 'author': {'familyName': None}, 'tags': ['example']}
EX3_RESULT = {'title': 'Hello!', 'author': {'givenName': 'John'}, 'tags': ['example'],
              'content': 'This will be unchanged', 'phoneNumber': '+01-123-456-7890'}

LOOKALIKES = ['\u0663', '\uff11', '\u00b2', '\u212a', '\u0131', '\u017f', '\u0660', '\u2467', '\u00a0', '\u2003', '\uff21', '\u0130', '\u037e', '\uff1b', '\uff1d',
              '\u201c', '\u2033', '\u2215', '\u2028', '\u0085', '\u1680', '\uff0c', '\uff01', '\uff1a', '\u212b', '\u2126', '\u1e9e', '\ufb01', '\uff0e', '\u2024',
              '\uff3f', '\u2010', '\u2212', '\uff5e', '\u2018', '\u2019', '\uff02', '\uff0f', '\uff1f', '\uff03', '\uff05', '\uff3b', '\uff3d', '\u2044', '\u00e9']
ARGSPEC = {'value_reason': [('value', {'a': 1})], 'type_name': [('value', {'a': 1})], 'canonical': [('value', {'a': 1})],
           'merge_equal': [('a', {'a': 1}), ('b', {'a': 1})], 'merge_patch': [('target', {'a': 1}), ('patch', {'a': 2})],
           'merge_patch_list': [('target', {'a': 1}), ('patches', [{'a': 2}])], 'merge_ops': [('target', {'a': 1}), ('patch', {'a': 2})],
           'removed_paths': [('patch', {'a': None})], 'diff': [('original', {'a': 1}), ('modified', {'a': 2})],
           'get_path': [('value', {'a': 1}), ('path', ('a',))]}
REJECT = {'type_name': ((object(),), 'bad_value:value.type'),
          'canonical': ((object(),), 'bad_value:value.type'),
          'merge_equal': ((object(), {'a': 1}), 'bad_value:a.type'),
          'merge_patch': ((object(), {}), 'bad_value:target.type'),
          'merge_patch_list': (({}, 'x'), 'bad_type:patches'),
          'merge_ops': ((object(), {}), 'bad_value:target.type'),
          'removed_paths': ((object(),), 'bad_value:patch.type'),
          'diff': ((object(), {}), 'bad_value:original.type'),
          'get_path': (({}, 'x'), 'bad_type:path')}

# ---- hostile values ----------------------------------------------------------------------------------------------
class S(str):
    pass


class T(tuple):
    pass


class D(dict):
    pass


class L(list):
    pass


class F(float):
    pass


class Meta(type):
    def __eq__(cls, other):
        return True

    def __hash__(cls):
        return 1


class SM(str, metaclass=Meta):
    pass


class EqAll(str):
    def __eq__(self, other):
        return True

    def __ne__(self, other):
        return False

    def __hash__(self):
        return 0


class BoolLike(int):
    pass


NAN = float('nan')
INF = float('inf')
STR_HOSTILE = [S('g'), SM('g'), EqAll('g')]
JUNK = [object(), ('a',), T(('a',)), b'g', bytearray(b'g'), {1, 2}, frozenset([1]), (lambda: 1),
        D(a=1), L([1]), F(1.5), BoolLike(1), S('x'), SM('x'), EqAll('x')]


def deep(n):
    v = []
    cur = v
    for _ in range(n - 1):
        nxt = []
        cur.append(nxt)
        cur = nxt
    return v


# ---- constants, shape ----------------------------------------------------------------------------------------------
def test_constants_exact():
    assert m.SCOPE == 'RFC 7396 JSON Merge Patch processing (section 2) over decoded caller-supplied values: validity, canonical form, equality, single and sequenced application, operation lists, removal paths, patch difference and path lookup'
    assert m.NOT_CLAIMED == ('standard', 'authority', 'certification', 'currency', 'completeness', 'text-grammar', 'http-patch-semantics', 'media-type-registration', 'authorization')
    assert m.CLAIMS == {'standard': False, 'authoritative': False, 'certified': False, 'current': False, 'complete': False,
                        'text_grammar': False, 'http_patch_semantics': False, 'media_type_registration': False, 'authorization': False}
    assert all(v is False for v in m.CLAIMS.values())
    assert m.DEPTH_CAP == 32 and m.NODE_CAP == 4096
    assert m.ADJACENT == ('RFC 8259 sections 2-7 JSON text grammar: parsing and serializing JSON text (b1214)',
                          'RFC 7464 JSON text sequences framing over the JSON grammar (b1176)',
                          'RFC 6902 JSON Patch operations and RFC 6901 JSON Pointer syntax (b1178)')
    assert m._REG == REG and m._INF == INF and m._NINF == -INF and m._INF != m._INF * 0


def test_order_docstrings_and_private_names():
    fns = [n for n, v in vars(m).items() if inspect.isfunction(v) and v.__module__ == m.__name__ and not n.startswith('_') and n != 'make_fail']
    assert tuple(fns) == NAMES
    for n in NAMES + PRIVATE + ('make_fail',):
        assert getattr(m, n).__doc__ is None, n
    assert m.__doc__ == DOC_EXACT
    for n in PRIVATE:
        assert inspect.isfunction(getattr(m, n))
    priv = tuple(n for n, v in vars(m).items() if inspect.isfunction(v) and v.__module__ == m.__name__ and n.startswith('_'))
    assert priv == PRIVATE


def test_header_quotes_are_in_the_header_and_distinct():
    flat = re.sub(r'\s+', ' ', m.__doc__)
    assert len(QUOTES) == len(set(QUOTES)) == 18
    for q in QUOTES:
        assert re.sub(r'\s+', ' ', q) in flat, q


def test_header_names_every_erratum_source_and_function():
    d = m.__doc__
    for tok in ('RFC 7396', 'RFC 8259', 'RFC 7159', 'RFC 7386', 'RFC 7464', 'RFC 6902', 'RFC 6901',
                '545e1d61667c243ea14d6b1a56212370a26d46e1acd441803805fcdecd9164c6',
                '61a5378f4255c720beb2a4b4a63b29540147c140f36988bf086291989b4cd2d7',
                '50aa72534210945457f5460a50f263c1d6cf87a3da8c814c1d9f54cb04f22342',
                '2771053324fcbbc3f775f4b6d7514c204ba1a4c65077c4fa866614d392640c66',
                '12791 bytes', '28360 bytes', '27451 bytes', '0 errata', '16 errata', '9 errata', '1 erratum',
                'Obsoleted by', 'Updated by', 'Obsoletes (1)',
                '5218', '5853', '7600', '7603', '7617', '6208', '7307', '7383', '8874', '7650', '8438', '7673',
                '5210', '8622', '5318', '9095', '3915', '3984', '3983', '4220', '4264', '4298', '4336', '4388', '8437', '4132'):
        assert tok in d, tok
    for n in NAMES:
        assert n in d, n
    for r in ('type', 'key', 'float.nan', 'float.inf', 'depth', 'nodes', 'patches.length', 'patches.item',
              'path.length', 'step.type', 'step.kind', 'path.missing', 'path.leaf'):
        assert r in d, r


# ---- source bans -------------------------------------------------------------------------------------------------
def _src():
    return open(MODPATH).read()


def test_module_imports_and_source_bans():
    tree = ast.parse(_src())
    mods = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods += [a.name for a in n.names]
        elif isinstance(n, ast.ImportFrom):
            mods.append(n.module)
    assert sorted(mods) == sorted(['importlib.util', 'app.modules.instinct_doc.p235_concepts_registry'])
    names = set()
    attrs = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Name):
            names.add(n.id)
        elif isinstance(n, ast.Attribute):
            attrs.add(n.attr)
    assert attrs == {'append', 'name', 'pop', 'sort'}
    for bad in ('re', 'copy', 'json', 'unicodedata', 'urllib', 'ipaddress', 'socket', 'os', 'sys', 'time', 'random', 'datetime', 'open', 'eval', 'exec',
                '__import__', 'input', 'print', 'ord', 'chr', 'isinstance', 'getattr', 'setattr', 'globals', 'locals', 'vars', 'hash', 'id', 'sorted',
                'reversed', 'map', 'filter', 'any', 'all', 'repr', 'format', 'sum', 'min', 'max', 'abs', 'divmod',
                'zip', 'enumerate', 'iter', 'next'):
        assert bad not in names, bad
    calls = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            if isinstance(n.func, ast.Name):
                calls.add(n.func.id)
            else:
                assert isinstance(n.func, ast.Attribute) and n.func.attr in ('append', 'pop', 'sort'), ast.dump(n.func)
    assert calls <= {'type', 'len', 'range', 'float', 'tuple', 'ValueError', 'make_fail', 'find_spec', 'fail'} | set(PRIVATE) | set(NAMES), calls
    for node in ast.walk(tree):
        assert not isinstance(node, (ast.Lambda, ast.Global, ast.Nonlocal, ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp, ast.Starred, ast.JoinedStr, ast.Await, ast.Yield))
    src = _src()
    banned = [' or ' + 'True', 'if ' + 'False', 'else ' + 'True', ' and ' + 'False', ' or ' + 'False']
    for b in banned:
        assert b not in src, b
    assert 'import *' not in src


def test_source_and_tests_have_no_vacuous_assertions():
    me = open(os.path.join(HERE, 'test_instinct_p235_concepts_batch1177_jsonmerge.py')).read()
    for b in (' or ' + 'True', 'if ' + 'False:', 'else ' + 'True', ' and ' + 'False', ' or ' + 'False', 'assert ' + 'True', 'assert ' + '1 ', 'assert ' + 'not ' + 'False'):
        assert b not in me, b


# ---- exact types: every hostile or wrong-typed input is refused without consulting it --------------------------------
def test_value_reason_classifies_junk_and_never_raises():
    for bad in JUNK:
        assert m.value_reason(bad) == 'type', bad
    assert m.value_reason(('a',)) == 'type' and m.value_reason(b'') == 'type'
    for good in (None, True, False, 0, 1, -7, 0.0, -1.5, '', 'x', [], {}, {'a': [1, {'b': None}]}, [None, [True]]):
        assert m.value_reason(good) == 'ok', good
    for fn, args, code in [(f,) + REJECT[f] for f in REJECT]:
        assert run(fn, *args) == E(fn, code), fn


@pytest.mark.parametrize('fn', [f for f in NAMES if f != 'value_reason'])
def test_hostile_subclass_values_are_refused_by_identity(fn):
    sig = ARGSPEC[fn]
    n = 0
    for pos, (name, good) in enumerate(sig):
        if name in ('patches', 'path'):
            continue
        for bad in (D(a=1), L([1]), F(1.5), BoolLike(1), S('x'), SM('x'), EqAll('x'), ('a',), object(), {1, 2}):
            args = [g for _n, g in sig]
            args[pos] = bad
            want = 'bad_value:%s.type' % name
            assert run(fn, *args) == E(fn, want), (fn, name, bad)
            n += 1
    assert n >= 9


def test_non_value_arguments_are_exact_types_by_identity():
    assert run('merge_patch_list', {}, ()) == E('merge_patch_list', 'bad_type:patches')
    assert run('merge_patch_list', {}, T(({},))) == E('merge_patch_list', 'bad_type:patches')
    assert run('merge_patch_list', {}, None) == E('merge_patch_list', 'bad_type:patches')
    assert run('get_path', {}, []) == E('get_path', 'bad_type:path')
    assert run('get_path', {}, L(['a'])) == E('get_path', 'bad_type:path')
    assert run('get_path', {}, 'a') == E('get_path', 'bad_type:path')
    assert run('get_path', {'a': 1}, (True,)) == E('get_path', 'bad_value:path.step.type')
    assert run('get_path', {'a': 1}, (False,)) == E('get_path', 'bad_value:path.step.type')
    assert run('get_path', {'a': 1}, (BoolLike(0),)) == E('get_path', 'bad_value:path.step.type')
    assert run('get_path', {'a': 1}, (S('a'),)) == E('get_path', 'bad_value:path.step.type')
    assert run('get_path', {'a': 1}, (1.5,)) == E('get_path', 'bad_value:path.step.type')
    assert run('get_path', {'a': 1}, (None,)) == E('get_path', 'bad_value:path.step.type')


def test_key_faults_beat_child_faults_and_str_subclass_keys_are_refused():
    assert m.value_reason({1: 'a'}) == 'key'
    assert m.value_reason({None: 'a'}) == 'key'
    assert m.value_reason({True: 'a'}) == 'key'
    assert m.value_reason({S('k'): 1}) == 'key'
    assert m.value_reason({SM('k'): NAN}) == 'key'
    assert m.value_reason({EqAll('k'): object()}) == 'key'
    assert m.value_reason({'a': NAN, 'b': {1: 'x'}}) == 'float.nan'
    assert m.value_reason({'a': {1: 'x'}, 'b': NAN}) == 'key'
    assert m.value_reason({'ok': {EqAll('k'): 1}}) == 'key'

# ---- semantics: tables, check order, both-bad pins, caps, fuzz -------------------------------------------------------
VR_CASES = [
    (None, 'ok'), (True, 'ok'), (False, 'ok'), (0, 'ok'), (-7, 'ok'), (1.5, 'ok'), (-0.0, 'ok'),
    ('', 'ok'), ('x', 'ok'), ([], 'ok'), ({}, 'ok'), ({'a': [1, {'b': None}]}, 'ok'),
    (2 ** 70, 'ok'), ('\U0001F600', 'ok'), ({'\u00e9': '\u2044'}, 'ok'),
    (NAN, 'float.nan'), (INF, 'float.inf'), (-INF, 'float.inf'),
    ({'a': NAN}, 'float.nan'), ([[INF]], 'float.inf'), ({'a': {'b': -INF}}, 'float.inf'),
    ((1,), 'type'), (b'x', 'type'), ({1}, 'type'), (object(), 'type'),
    ({1: 'a'}, 'key'), ({'a': 1, 2: 'b'}, 'key'), ([{3: 'x'}], 'key'),
]


@pytest.mark.parametrize('v,want', VR_CASES)
def test_value_reason_table(v, want):
    assert m.value_reason(v) == want


def test_value_reason_caps_pinned_at_cap_and_cap_plus_one():
    assert m.value_reason(deep(32)) == 'ok'
    assert m.value_reason(deep(33)) == 'depth'
    d = {'a': 1}
    cur = d
    for _ in range(31):
        nxt = {'a': 1}
        cur['z'] = nxt
        cur = nxt
    assert m.value_reason(d) == 'ok'
    cur['z'] = {'a': 1}
    assert m.value_reason(d) == 'depth'
    assert m.value_reason([0] * 4095) == 'ok'
    assert m.value_reason([0] * 4096) == 'nodes'
    wide = {'k' + str(i): i for i in range(4095)}
    assert m.value_reason(wide) == 'ok'
    wide['k4095'] = 1
    assert m.value_reason(wide) == 'nodes'


def test_value_reason_both_bad_pins():
    assert m.value_reason(deep(33)) == 'depth'
    chain = deep(32)
    inner = chain
    while len(inner) == 1:
        inner = inner[0]
    inner.append([object()])
    assert m.value_reason(chain) == 'depth'
    over = [0] * 4096 + [object()]
    assert m.value_reason(over) == 'nodes'
    assert m.value_reason({'k': NAN, 1: 'x'}) == 'key'
    # The running count crosses NODE_CAP exactly when a faulty object is
    # popped: nodes is reported before that object's names are checked
    # (the order the header states: depth, then nodes, then key). Only the
    # key's type is a fault: an overlong key string is data, not a fault.
    assert m.value_reason([0] * 4095 + [{1: 'x'}]) == 'nodes'
    assert m.value_reason({'k' * 70000: 1}) == 'ok'
    # A container popped at depth DEPTH_CAP + 1 reports depth even when the
    # count would cross NODE_CAP at the same pop (depth is checked first).
    node = []
    for i in range(32):
        node = [0] * (126 if i == 0 else 127) + [node]
    assert m.value_reason(node) == 'depth'


def test_value_reason_float_pins():
    assert m.value_reason(1e308) == 'ok'
    assert m.value_reason(-1e308) == 'ok'
    assert m.value_reason(1e309) == 'float.inf'
    assert m.value_reason(-1e309) == 'float.inf'
    assert m.value_reason(0.0) == 'ok' and m.value_reason(-0.0) == 'ok'
    assert m.value_reason({'a': [{'b': [NAN]}]}) == 'float.nan'


def test_type_name_table():
    assert m.type_name({}) == 'object' and m.type_name({'a': 1}) == 'object'
    assert m.type_name([]) == 'array' and m.type_name([None]) == 'array'
    assert m.type_name('') == 'string' and m.type_name('\u00e9') == 'string'
    assert m.type_name(0) == 'number' and m.type_name(-0.0) == 'number' and m.type_name(2 ** 70) == 'number'
    assert m.type_name(True) == 'true' and m.type_name(False) == 'false'
    assert m.type_name(None) == 'null'
    assert run('type_name', NAN) == E('type_name', 'bad_value:value.float.nan')
    assert run('type_name', {1: 'a'}) == E('type_name', 'bad_value:value.key')


def test_canonical_sorts_recursively_by_code_point():
    c = m.canonical({'b': 1, 'a': {'y': 2, 'x': [{'b': 1, 'a': 2}]}})
    assert list(c) == ['a', 'b'] and list(c['a']) == ['x', 'y'] and list(c['a']['x'][0]) == ['a', 'b']
    c2 = m.canonical({'\u00e9': 1, 'a': 2, 'Z': 3})
    assert list(c2) == ['Z', 'a', '\u00e9']
    src = {'b': [3, {'d': 4, 'c': 5}], 'a': 1}
    out = m.canonical(src)
    assert list(src) == ['b', 'a'] and list(src['b'][1]) == ['d', 'c']
    assert out is not src and out['b'] is not src['b'] and out['b'][1] is not src['b'][1]
    assert m.canonical([{'b': 1, 'a': 2}, {'d': 3, 'c': 4}])[0] == {'a': 2, 'b': 1}
    assert m.canonical(5) == 5 and m.canonical(None) is None and m.canonical('x') == 'x'
    for ch in LOOKALIKES:
        got = m.canonical({'z': 1, ch: 2})
        assert list(got) == sorted(['z', ch]), repr(ch)


def test_merge_equal_table():
    assert m.merge_equal(1, 1.0) is True
    assert m.merge_equal(-0.0, 0) is True
    assert m.merge_equal(2 ** 70, float(2 ** 70)) is True
    assert m.merge_equal(True, 1) is False
    assert m.merge_equal(False, 0) is False
    assert m.merge_equal(True, True) is True
    assert m.merge_equal(None, None) is True
    assert m.merge_equal(None, 0) is False
    assert m.merge_equal('', None) is False
    assert m.merge_equal({'a': 1, 'b': [1, 2]}, {'b': [1, 2], 'a': 1.0}) is True
    assert m.merge_equal({'a': 1}, {'a': 2}) is False
    assert m.merge_equal({'a': 1}, {'a': 1, 'b': 2}) is False
    assert m.merge_equal({'a': 1, 'b': 2}, {'a': 1}) is False
    assert m.merge_equal([1, [2]], [1, [2.0]]) is True
    assert m.merge_equal([1, 2], [2, 1]) is False
    assert m.merge_equal({'a': True}, {'a': 1}) is False
    assert m.merge_equal('1', 1) is False
    assert run('merge_equal', object(), {}) == E('merge_equal', 'bad_value:a.type')
    assert run('merge_equal', {}, object()) == E('merge_equal', 'bad_value:b.type')
    assert run('merge_equal', {}, INF) == E('merge_equal', 'bad_value:b.float.inf')


@pytest.mark.parametrize('orig,patch,want', APPENDIX_A)
def test_appendix_a_all_fifteen_cases(orig, patch, want):
    o2 = copy.deepcopy(orig)
    p2 = copy.deepcopy(patch)
    got = m.merge_patch(orig, patch)
    assert got == want
    assert orig == o2 and patch == p2


def test_section3_example_with_member_order():
    got = m.merge_patch(copy.deepcopy(EX3_TARGET), copy.deepcopy(EX3_PATCH))
    assert got == EX3_RESULT
    assert list(got) == ['title', 'author', 'tags', 'content', 'phoneNumber']
    assert list(got['author']) == ['givenName']


def test_merge_patch_is_fresh_and_never_mutates():
    t = {'a': {'b': 1}, 'c': [1, 2]}
    p = {'a': {'d': 2}, 'c': [3]}
    got = m.merge_patch(t, p)
    assert got == {'a': {'b': 1, 'd': 2}, 'c': [3]}
    assert got['a'] is not t['a'] and got['c'] is not t['c'] and got['c'] is not p['c']
    assert t == {'a': {'b': 1}, 'c': [1, 2]} and p == {'a': {'d': 2}, 'c': [3]}
    got2 = m.merge_patch(t, p)
    assert got2 == got and got2['a'] is not got['a']


def test_merge_patch_list_sequences_and_validation():
    assert m.merge_patch_list({'a': 1}, []) == {'a': 1}
    assert m.merge_patch_list({'a': 1}, [{'b': 2}, {'a': None}, {'c': {'d': 3}}]) == {'b': 2, 'c': {'d': 3}}
    assert m.merge_patch_list({}, [{'a': {'bb': {'ccc': None}}}]) == {'a': {'bb': {}}}
    out = m.merge_patch_list({'a': [1]}, [])
    assert out == {'a': [1]} and out['a'] is not None
    assert run('merge_patch_list', object(), []) == E('merge_patch_list', 'bad_value:target.type')
    assert run('merge_patch_list', {}, [{}] * 4097) == E('merge_patch_list', 'bad_value:patches.length')
    assert run('merge_patch_list', {}, [{}, {'x': NAN}]) == E('merge_patch_list', 'bad_value:patches.item.float.nan')
    assert run('merge_patch_list', {}, [{1: 'a'}, {'x': INF}]) == E('merge_patch_list', 'bad_value:patches.item.key')
    assert m.merge_patch_list({}, [{}] * 4096) == {}
    assert run('merge_patch_list', {'a': object()}, 'x') == E('merge_patch_list', 'bad_value:target.type')


def test_merge_ops_tables():
    assert m.merge_ops({'a': 'b'}, {'a': None}) == (('remove', ('a',)),)
    assert m.merge_ops({'a': 'b'}, {'b': None}) == ()
    assert m.merge_ops({'e': None}, {'a': 1}) == (('set', ('a',), 1),)
    assert m.merge_ops({'a': 'foo'}, None) == (('set', (), None),)
    assert m.merge_ops(['a', 'b'], ['c', 'd']) == (('set', (), ['c', 'd']),)
    assert m.merge_ops({}, {'a': {'bb': {'ccc': None}}}) == (('set', ('a',), {'bb': {}}),)
    assert m.merge_ops([1, 2], {'a': 'b', 'c': None}) == (('set', ('a',), 'b'),)
    assert m.merge_ops({'a': {'b': 'c'}}, {'a': {'b': 'd', 'c': None}}) == (('set', ('a', 'b'), 'd'),)
    ops = m.merge_ops(copy.deepcopy(EX3_TARGET), copy.deepcopy(EX3_PATCH))
    assert ops == (('set', ('title',), 'Hello!'),
                   ('set', ('phoneNumber',), '+01-123-456-7890'),
                   ('remove', ('author', 'familyName')),
                   ('set', ('tags',), ['example']))
    got = m.merge_ops({'a': {'x': 1}}, {'a': {'y': None}, 'b': {'z': None}})
    assert got == (('set', ('b',), {}),)
    op = m.merge_ops({}, {'a': [{'b': 1}]})
    assert op == (('set', ('a',), [{'b': 1}]),)
    assert op[0][2] is not None and op[0][2][0] is not None
    p = {'a': [{'b': 1}]}
    op2 = m.merge_ops({}, p)
    assert op2[0][2][0] is not p['a'][0]


def test_removed_paths_tables():
    assert m.removed_paths({'a': None}) == (('a',),)
    assert m.removed_paths({'a': {'bb': {'ccc': None}}}) == (('a', 'bb', 'ccc'),)
    assert m.removed_paths(['c']) == ()
    assert m.removed_paths(None) == ()
    assert m.removed_paths({'a': {'b': None, 'c': {'d': None}}, 'e': None}) == (('a', 'b'), ('a', 'c', 'd'), ('e',))
    assert m.removed_paths({'a': [None]}) == ()
    assert m.removed_paths({}) == ()
    assert run('removed_paths', NAN) == E('removed_paths', 'bad_value:patch.float.nan')


def test_diff_tables_and_member_order():
    assert m.diff({'a': 'b'}, {'a': 'b'}) == {}
    assert m.diff(1, 1.0) == 1.0
    assert m.diff({'a': 'b'}, {'a': 'c'}) == {'a': 'c'}
    assert m.diff({'a': 'b', 'b': 'c'}, {'a': 'b'}) == {'b': None}
    assert m.diff({'a': 'b'}, {'a': 'b', 'c': 1}) == {'c': 1}
    assert m.diff({'a': {'x': 1, 'y': 2}}, {'a': {'x': 1, 'y': 3}}) == {'a': {'y': 3}}
    assert m.diff(1, {'a': 1}) == {'a': 1}
    assert m.diff({'a': 1}, 2) == 2
    assert m.diff([1], [1, 2]) == [1, 2]
    assert m.diff({'a': 1}, None) is None
    d = m.diff({'b': 1, 'a': 2}, {'a': 3, 'c': 4})
    assert d == {'a': 3, 'c': 4, 'b': None} and list(d) == ['a', 'c', 'b']
    assert m.diff({'a': {'b': {'c': 1}}}, {'a': {'b': {'c': 1}}}) == {}
    for orig, patch, want in APPENDIX_A:
        assert m.merge_patch(orig, m.diff(orig, want)) == want, (orig, want)


def test_diff_limitation_is_pinned():
    d1 = m.diff({'a': 1}, {'a': None})
    assert d1 == {'a': None}
    assert m.merge_patch({'a': 1}, d1) == {} != {'a': None}
    d2 = m.diff({}, {'a': {'b': None}})
    assert d2 == {'a': {'b': None}}
    assert m.merge_patch({}, d2) == {'a': {}} != {'a': {'b': None}}
    d3 = m.diff({'k': {'x': 1}}, {'k': {'b': None}})
    assert d3 == {'k': {'b': None, 'x': None}}
    assert m.merge_patch({'k': {'x': 1}}, d3) == {'k': {}} != {'k': {'b': None}}


def test_get_path_tables():
    v = {'a': [1, {'b': 2}], 'c': None}
    assert m.get_path(v, ('a', 1, 'b')) == 2
    assert m.get_path(v, ()) is v
    assert m.get_path(v, ('c',)) is None
    assert m.get_path(v, ('a', 0)) == 1
    assert m.get_path([[['x']]], (0, 0, 0)) == 'x'
    assert run('get_path', v, ('a', 2)) == E('get_path', 'bad_value:path.missing')
    assert run('get_path', v, ('a', -1)) == E('get_path', 'bad_value:path.missing')
    assert run('get_path', v, ('b',)) == E('get_path', 'bad_value:path.missing')
    assert run('get_path', v, ('a', 'b')) == E('get_path', 'bad_value:path.step.kind')
    assert run('get_path', v, (0,)) == E('get_path', 'bad_value:path.step.kind')
    assert run('get_path', v, ('a', 0, 'x')) == E('get_path', 'bad_value:path.leaf')
    assert run('get_path', 1, ('a',)) == E('get_path', 'bad_value:path.leaf')
    assert run('get_path', [True], (True,)) == E('get_path', 'bad_value:path.step.type')
    assert run('get_path', {'a': 1}, ('a', 'b')) == E('get_path', 'bad_value:path.leaf')
    assert run('get_path', object(), ()) == E('get_path', 'bad_value:value.type')
    assert run('get_path', {}, ('a',) * 4097) == E('get_path', 'bad_value:path.length')
    assert run('get_path', {'a': 1}, ('a',) * 4096) == E('get_path', 'bad_value:path.leaf')


def test_get_path_deep_path_at_cap():
    p = ('a',) * 32
    v = {}
    cur = v
    for _ in range(31):
        cur['a'] = {}
        cur = cur['a']
    cur['a'] = 'hit'
    assert m.get_path(v, p) == 'hit'
    assert run('get_path', v, ('a',) * 33)[0] == 'err'
    assert run('get_path', v, ('a',) * 33) == E('get_path', 'bad_value:path.leaf')


# ---- memory: the length caps are checked before any work --------------------------------------------------------------
def test_length_caps_are_checked_before_any_allocation_or_scan():
    big_patches = [{}] * 4097
    big_path = ('a',) * 4097
    tracemalloc.start()
    try:
        tracemalloc.clear_traces()
        tracemalloc.reset_peak()
        base = tracemalloc.get_traced_memory()[0]
        r = run('merge_patch_list', {}, big_patches)
        peak = tracemalloc.get_traced_memory()[1] - base
        assert r == E('merge_patch_list', 'bad_value:patches.length') and peak < 4000, peak
        tracemalloc.clear_traces()
        tracemalloc.reset_peak()
        base = tracemalloc.get_traced_memory()[0]
        r = run('get_path', {}, big_path)
        peak = tracemalloc.get_traced_memory()[1] - base
        assert r == E('get_path', 'bad_value:path.length') and peak < 4000, peak
    finally:
        tracemalloc.stop()


# ---- non-ASCII is data, not an error -----------------------------------------------------------------------------------
def test_non_ascii_strings_and_keys_are_valid_data():
    for ch in LOOKALIKES:
        assert m.value_reason(ch) == 'ok'
        assert m.value_reason({ch: [ch]}) == 'ok'
        assert m.type_name(ch) == 'string'
        assert m.merge_patch({'a': 1}, {ch: 2}) == {'a': 1, ch: 2}
        assert m.get_path({ch: 5}, (ch,)) == 5
    assert m.value_reason({'\u0663': '\uff11'}) == 'ok'


def test_results_are_fresh_exact_types():
    assert type(m.value_reason({})) is str
    assert type(m.type_name({})) is str
    assert type(m.canonical({})) is dict
    assert type(m.merge_equal(1, 1)) is bool
    assert type(m.merge_patch({}, {})) is dict
    assert type(m.merge_patch_list({}, [])) is dict
    assert type(m.merge_ops({}, {})) is tuple
    assert type(m.removed_paths({})) is tuple
    assert type(m.diff(1, 2)) is int
    ops = m.merge_ops({'a': 1}, {'a': None})
    assert type(ops[0]) is tuple and type(ops[0][1]) is tuple and type(ops[0][0]) is str


def test_depth_pins_mixed_container_chains():
    ld = []
    cur = ld
    for _ in range(30):
        nxt = []
        cur.append(nxt)
        cur = nxt
    cur.append({})
    assert m.value_reason(ld) == 'ok'
    cur[0] = []
    cur[0].append({})
    assert m.value_reason(ld) == 'depth'
    dd = {}
    curd = dd
    for _ in range(30):
        nxt = {}
        curd['z'] = nxt
        curd = nxt
    curd['z'] = []
    assert m.value_reason(dd) == 'ok'
    curd['z'] = [{}]
    assert m.value_reason(dd) == 'depth'


def test_merge_equal_bool_never_equals_number_inside_lists():
    assert m.merge_equal([True], [1]) is False
    assert m.merge_equal([1], [True]) is False
    assert m.merge_equal([[True]], [[1]]) is False
    assert m.merge_equal([False], [0]) is False
    assert m.merge_equal([True], [True]) is True
    assert m.merge_equal({'a': [True]}, {'a': [1]}) is False


def test_check_order_both_bad_pins():
    assert run('merge_equal', object(), INF) == E('merge_equal', 'bad_value:a.type')
    assert run('merge_equal', {1: 'a'}, object()) == E('merge_equal', 'bad_value:a.key')
    assert run('merge_patch', object(), {1: 'a'}) == E('merge_patch', 'bad_value:target.type')
    assert run('merge_patch', {'t': 1}, {1: 'a'}) == E('merge_patch', 'bad_value:patch.key')
    assert run('merge_ops', object(), {1: 'a'}) == E('merge_ops', 'bad_value:target.type')
    assert run('merge_ops', {'t': 1}, {1: 'a'}) == E('merge_ops', 'bad_value:patch.key')
    assert run('diff', object(), INF) == E('diff', 'bad_value:original.type')
    assert run('diff', {'o': 1}, INF) == E('diff', 'bad_value:modified.float.inf')
    assert run('get_path', object(), 'x') == E('get_path', 'bad_value:value.type')
    assert run('get_path', {'v': 1}, 'x' * 4097) == E('get_path', 'bad_type:path')
    assert run('get_path', {'v': 1}, ['a'] * 4097) == E('get_path', 'bad_type:path')
    assert run('merge_patch_list', object(), 'x') == E('merge_patch_list', 'bad_value:target.type')
    assert run('merge_patch_list', {'t': 1}, 'x') == E('merge_patch_list', 'bad_type:patches')
    assert run('merge_patch_list', {}, [{}] * 4096 + [{'x': NAN}]) == E('merge_patch_list', 'bad_value:patches.length')
    assert run('merge_patch_list', {}, [{'x': NAN}] + [{}] * 4096) == E('merge_patch_list', 'bad_value:patches.length')

# ---- fuzz: independent oracles, 1200 iterations per seed ---------------------------------------------------------------
def _fz_scalar(rng):
    return rng.choice([None, True, False, 0, 1, -3, 2 ** 70, 0.5, -0.0, 1e10, '', 'a', 'q"x', '\\', 'é', '⁄'])


def _fz_value(rng, d, member_nulls=True):
    if d <= 0 or rng.random() < 0.42:
        return _fz_scalar(rng)
    if rng.random() < 0.5:
        return [_fz_value(rng, d - 1, member_nulls) for _ in range(rng.randrange(4))]
    out = {}
    for _ in range(rng.randrange(4)):
        k = rng.choice(['a', 'b', 'c', 'é', 'x y', '​'])
        v = _fz_value(rng, d - 1, member_nulls)
        if v is None and not member_nulls:
            v = 0
        out[k] = v
    return out


def test_fuzz_merge_patch_against_oracle_1200_iterations():
    rng = random.Random(1177)
    for _ in range(1200):
        t = _fz_value(rng, 5)
        p = _fz_value(rng, 5)
        t2 = copy.deepcopy(t)
        p2 = copy.deepcopy(p)
        got = m.merge_patch(t, p)
        assert o_eq(got, o_merge(t, p)), (t, p, got)
        assert o_eq(t, t2) and o_eq(p, p2), (t, p)
        assert m.value_reason(got) == 'ok'


def test_fuzz_merge_ops_apply_removed_paths_1200_iterations():
    rng = random.Random(1178)
    for _ in range(1200):
        t = _fz_value(rng, 5)
        p = _fz_value(rng, 5)
        ops = m.merge_ops(t, p)
        assert o_eq(o_apply_ops(t, p, ops), m.merge_patch(t, p)), (t, p, ops)
        assert [op[1] for op in ops if op[0] == 'remove'] == o_remove_hits(t, p), (t, p, ops)
        static = m.removed_paths(p)
        for path in [op[1] for op in ops if op[0] == 'remove']:
            assert path in static, (t, p, ops)
        for op in ops:
            assert op[0] in ('set', 'remove') and type(op[1]) is tuple
            if op[0] == 'set':
                assert m.value_reason(op[2]) == 'ok'


def test_fuzz_diff_roundtrip_1200_iterations():
    rng = random.Random(1179)
    for _ in range(1200):
        o = _fz_value(rng, 5)
        n = _fz_value(rng, 5, member_nulls=False)
        d = m.diff(o, n)
        assert m.value_reason(d) == 'ok', (o, n, d)
        assert m.merge_equal(m.merge_patch(o, d), n), (o, n, d)
        if m.merge_equal(o, n):
            if type(o) is dict and type(n) is dict:
                assert d == {}
            else:
                assert m.merge_equal(d, n)
        assert m.merge_equal(o, n) == o_eq(o, n)
        c = m.canonical(o)
        assert m.canonical(c) == c and m.merge_equal(c, o)


def _fz_hostile(rng, d):
    r = rng.random()
    if d <= 0 or r < 0.35:
        return rng.choice(JUNK + [NAN, INF, -INF, None, True, 1, 'x', 1.5])
    if r < 0.65:
        return [_fz_hostile(rng, d - 1) for _ in range(rng.randrange(3))]
    out = {}
    for _ in range(rng.randrange(3)):
        k = rng.choice(['a', 'b', S('k'), EqAll('k'), 2, None])
        out[k] = _fz_hostile(rng, d - 1)
    return out


def test_fuzz_value_reason_against_oracle_1200_iterations_mixed_junk():
    rng = random.Random(1180)
    for _ in range(1200):
        v = _fz_hostile(rng, 4)
        want = o_check(v)
        assert m.value_reason(v) == want, (v, want, m.value_reason(v))
        if want != 'ok':
            assert run('type_name', v) == E('type_name', 'bad_value:value.' + want), (v, want)


def test_fuzz_canonical_equality_properties_1200_iterations():
    rng = random.Random(1181)
    for _ in range(1200):
        v = _fz_value(rng, 4)
        c = m.canonical(v)
        assert m.merge_equal(c, v)
        assert m.canonical(c) == c
        names = m.type_name(v)
        want = {'dict': 'object', 'list': 'array', 'str': 'string', 'int': 'number', 'float': 'number',
                'bool': ('true' if v else 'false'), 'NoneType': 'null'}[type(v).__name__]
        assert names == want


def test_a40_rev1_pins():
    # A40 FINAL (rev0 audit): three non-equivalent survivors, tests-only pins.
    # 1) L224_for1 (env line 224, inner _ops recursion loop): a nested
    # dict-dict merge must keep EVERY inner op, not just the first.
    assert m.merge_ops({'a': {}}, {'a': {'x': 1, 'y': 2}}) == (
        ('set', ('a', 'x'), 1), ('set', ('a', 'y'), 2))
    assert m.merge_ops({'a': {'p': 0}}, {'a': {'x': 1, 'y': 2, 'z': 3}}) == (
        ('set', ('a', 'x'), 1), ('set', ('a', 'y'), 2), ('set', ('a', 'z'), 3))
    assert m.merge_ops({'a': {'b': {}}}, {'a': {'b': {'x': 1, 'y': 2}}}) == (
        ('set', ('a', 'b', 'x'), 1), ('set', ('a', 'b', 'y'), 2))
    # 2) diff_eq_copy: diff of equal non-dict containers returns a fresh copy
    # sharing no mutable structure with either input.
    o = [1, {'a': 2}]
    n = [1, {'a': 2}]
    r = m.diff(o, n)
    assert r == [1, {'a': 2}]
    assert r is not o and r is not n
    assert r[1] is not o[1] and r[1] is not n[1]
    r[1]['b'] = 99
    r.append(7)
    assert o == [1, {'a': 2}] and n == [1, {'a': 2}]
    r2 = m.diff([1], [2, {'c': 3}])
    assert r2 == [2, {'c': 3}]
    assert r2[1] is not None
    src = [2, {'c': 3}]
    r3 = m.diff([1], src)
    assert r3 is not src and r3[1] is not src[1]
    r3[1]['d'] = 4
    assert src == [2, {'c': 3}]
    # 3) mpl_fresh: merge_patch_list with no patches returns a fresh copy,
    # never the target or its nested structures.
    t = {'a': [1, 2]}
    r = m.merge_patch_list(t, [])
    assert r == {'a': [1, 2]}
    assert r is not t
    assert r['a'] is not t['a']
    r['a'].append(3)
    r['b'] = 9
    assert t == {'a': [1, 2]}


# ---- registry guard, import log, namespace ----------------------------------------------------------------------
def test_registry_absent_uses_local_fallback(mp):
    mp.setitem(sys.modules, REG, None)
    mod = fresh()
    assert mod.make_fail.__module__ == mod.__name__
    with pytest.raises(ValueError) as e:
        mod.make_fail('x')('c')
    assert str(e.value) == 'P235:x:c'
    assert run('type_name', object(), mod=mod) == ('err', 'P235:type_name:bad_value:value.type')


def test_registry_present_is_used_by_every_function(mp):
    fake = types.ModuleType(REG)
    fake.make_fail = lambda name: (lambda code: (_ for _ in ()).throw(ValueError('FAKE:%s:%s' % (name, code))))
    mp.setitem(sys.modules, REG, fake)
    mod = fresh()
    assert mod.make_fail is fake.make_fail
    for fn in NAMES:
        if fn == 'value_reason':
            continue
        args, code = REJECT[fn]
        assert run(fn, *args, mod=mod) == ('err', 'FAKE:%s:%s' % (fn, code))


def test_registry_guard_foreign_name_never_consults_find_spec(mp):
    real = builtins.__import__
    spied = []
    err = ModuleNotFoundError('foreign', name='some.other.module')

    def hook(n, g=None, l=None, fromlist=(), level=0):
        if n == REG:
            raise err
        return real(n, g, l, fromlist, level)
    mp.setitem(sys.modules, REG, None)
    mp.setattr(importlib.util, 'find_spec', lambda name: spied.append(name) or object())
    mp.setattr(builtins, '__import__', hook)
    with pytest.raises(ModuleNotFoundError) as e:
        fresh()
    assert e.value is err and spied == []


def test_registry_guard_registry_name_with_spec_found_is_reraised(mp):
    real = builtins.__import__
    spied = []
    err = ModuleNotFoundError('inner', name=REG)

    def hook(n, g=None, l=None, fromlist=(), level=0):
        if n == REG:
            raise err
        return real(n, g, l, fromlist, level)
    mp.setitem(sys.modules, REG, None)
    mp.setattr(importlib.util, 'find_spec', lambda name: spied.append(name) or object())
    mp.setattr(builtins, '__import__', hook)
    with pytest.raises(ModuleNotFoundError) as e:
        fresh()
    assert e.value is err and spied == [REG]


@pytest.mark.parametrize('nm', [REG, 'some.other.module'])
def test_import_error_is_not_a_module_not_found_error(mp, nm):
    real = builtins.__import__
    err = ImportError('x', name=nm)

    def hook(n, g=None, l=None, fromlist=(), level=0):
        if n == REG:
            raise err
        return real(n, g, l, fromlist, level)
    mp.setitem(sys.modules, REG, None)
    mp.setattr(importlib.util, 'find_spec', lambda n: None)
    mp.setattr(builtins, '__import__', hook)
    with pytest.raises(ImportError) as e:
        fresh()
    assert e.value is err and type(e.value) is ImportError


IMPORTS = [('importlib.util', ('find_spec',), 0), (REG, ('make_fail',), 0)]
NAMESPACE = (['find_spec'] + ['SCOPE', 'NOT_CLAIMED', 'CLAIMS', 'ADJACENT', 'DEPTH_CAP', 'NODE_CAP', '_INF', '_NINF', '_REG', 'make_fail']
             + list(PRIVATE) + list(NAMES))
CALLS = []
for _fn in NAMES:
    _good = tuple(g for _n, g in ARGSPEC[_fn])
    if _fn == 'value_reason':
        CALLS.append((_fn, _good, (NAN,)))
    else:
        CALLS.append((_fn, _good, REJECT[_fn][0]))


@pytest.mark.parametrize('world', ['absent', 'foreign', 'registry_raise', 'present'])
def test_import_log_and_namespace_on_every_path(mp, world):
    real = builtins.__import__
    seen = []
    spied = []
    err = ModuleNotFoundError('x', name=('some.other.module' if world == 'foreign' else REG))
    fake = types.ModuleType(REG)
    fake.make_fail = lambda name: (lambda code: (_ for _ in ()).throw(ValueError('FAKE')))

    def spy(name):
        spied.append(name)
        return None if world == 'absent' else object()

    def hook(n, g=None, l=None, fromlist=(), level=0):
        if g is not None and g.get('__name__') == fresh.__defaults__[0]:
            seen.append((n, tuple(fromlist or ()), level))
        if n == REG and world in ('foreign', 'registry_raise'):
            raise err
        return real(n, g, l, fromlist, level)
    mp.setitem(sys.modules, REG, fake if world == 'present' else None)
    mp.setattr(importlib.util, 'find_spec', spy)
    mp.setattr(builtins, '__import__', hook)
    if world in ('foreign', 'registry_raise'):
        with pytest.raises(ModuleNotFoundError) as e:
            fresh()
        assert e.value is err
        assert seen == IMPORTS
        assert spied == ([] if world == 'foreign' else [REG])
        return
    mod = fresh()
    assert seen == IMPORTS
    assert spied == ([REG] if world == 'absent' else [])
    names = sorted(k for k in vars(mod) if not (k.startswith('__') and k.endswith('__')))
    assert names == sorted(NAMESPACE)
    del seen[:]
    for fn, good, bad in CALLS:
        for args in (good, bad):
            try:
                getattr(mod, fn)(*args)
            except ValueError:
                pass
    assert seen == []


def test_failure_prefix_is_p235_when_the_fallback_is_bound():
    if m.make_fail.__module__ == m.__name__:
        assert PFX == 'P235:'
    assert PFX.endswith(':') and 'x:c' not in PFX


# ---- the shared corpus: every refusal code of every public function ----------------------------------------------
CORPUS = []
for _fn, (_args, _code) in REJECT.items():
    CORPUS.append((_fn, _args, _code))
CORPUS += [
    ('type_name', ({1: 'a'},), 'bad_value:value.key'),
    ('type_name', (NAN,), 'bad_value:value.float.nan'),
    ('type_name', (INF,), 'bad_value:value.float.inf'),
    ('type_name', (deep(33),), 'bad_value:value.depth'),
    ('type_name', ([0] * 4096,), 'bad_value:value.nodes'),
    ('canonical', (deep(33),), 'bad_value:value.depth'),
    ('merge_equal', ({'a': NAN}, {}), 'bad_value:a.float.nan'),
    ('merge_equal', ({}, {1: 'x'}), 'bad_value:b.key'),
    ('merge_patch', (INF, {}), 'bad_value:target.float.inf'),
    ('merge_patch', ({}, deep(33)), 'bad_value:patch.depth'),
    ('merge_patch_list', (object(), []), 'bad_value:target.type'),
    ('merge_patch_list', ({}, [{}] * 4097), 'bad_value:patches.length'),
    ('merge_patch_list', ({}, [{}, {'x': NAN}]), 'bad_value:patches.item.float.nan'),
    ('merge_patch_list', ({}, [{1: 'a'}, {'x': INF}]), 'bad_value:patches.item.key'),
    ('merge_ops', ({}, {1: 'a'}), 'bad_value:patch.key'),
    ('removed_paths', ([0] * 4096,), 'bad_value:patch.nodes'),
    ('diff', ({}, INF), 'bad_value:modified.float.inf'),
    ('diff', (deep(33), {}), 'bad_value:original.depth'),
    ('get_path', (object(), ()), 'bad_value:value.type'),
    ('get_path', ({}, []), 'bad_type:path'),
    ('get_path', ({}, ('a',) * 4097), 'bad_value:path.length'),
    ('get_path', ({'a': 1}, (True,)), 'bad_value:path.step.type'),
    ('get_path', ({'a': 1}, (1.5,)), 'bad_value:path.step.type'),
    ('get_path', ({'a': 1}, (0,)), 'bad_value:path.step.kind'),
    ('get_path', ([1], ('a',)), 'bad_value:path.step.kind'),
    ('get_path', ({}, ('a',)), 'bad_value:path.missing'),
    ('get_path', ([1], (-1,)), 'bad_value:path.missing'),
    ('get_path', ([1], (5,)), 'bad_value:path.missing'),
    ('get_path', (1, ('a',)), 'bad_value:path.leaf'),
]
SUCCESS = [
    ('value_reason', ({'a': [1, None]},), 'ok'), ('value_reason', (NAN,), 'float.nan'),
    ('value_reason', ({1: 'a'},), 'key'), ('value_reason', (deep(33),), 'depth'),
    ('value_reason', ((1,),), 'type'), ('value_reason', (-INF,), 'float.inf'),
    ('value_reason', ([0] * 4096,), 'nodes'),
    ('type_name', (True,), 'true'), ('type_name', (False,), 'false'), ('type_name', (None,), 'null'),
    ('type_name', (1.5,), 'number'), ('type_name', ('',), 'string'), ('type_name', ([],), 'array'), ('type_name', ({},), 'object'),
    ('canonical', ({'b': 1, 'a': 2},), {'a': 2, 'b': 1}), ('canonical', (5,), 5),
    ('merge_equal', (1, 1.0), True), ('merge_equal', (True, 1), False), ('merge_equal', (None, None), True),
    ('merge_patch', ({'a': 'b'}, {'a': None}), {}), ('merge_patch', ({'a': 'foo'}, 'bar'), 'bar'),
    ('merge_patch_list', ({'a': 1}, []), {'a': 1}),
    ('merge_ops', ({'a': 'b'}, {'a': None}), (('remove', ('a',)),)),
    ('merge_ops', ({'a': 'foo'}, None), (('set', (), None),)),
    ('removed_paths', ({'a': None},), (('a',),)), ('removed_paths', (['c'],), ()),
    ('diff', ({'a': 1}, {'a': 2}), {'a': 2}), ('diff', ({'a': 1}, {'a': 1.0}), {}),
    ('get_path', ({'a': [1]}, ('a', 0)), 1),
]


def drive(mod, pfx=None):
    p = PFX if pfx is None else pfx
    for fn, args, want in CORPUS:
        with pytest.raises(ValueError) as e:
            getattr(mod, fn)(*args)
        assert str(e.value) == p + fn + ':' + want
    for fn, args, want in SUCCESS:
        assert getattr(mod, fn)(*args) == want


def test_corpus_reaches_every_refusal_code_and_every_success_branch():
    drive(m)
    codes = {(fn, w) for fn, a, w in CORPUS}
    for fn, (args, code) in REJECT.items():
        assert (fn, code) in codes
    for r in ('key', 'float.nan', 'float.inf', 'depth', 'nodes'):
        assert ('type_name', 'bad_value:value.' + r) in codes
    for r in ('patches.length', 'patches.item.float.nan', 'patches.item.key'):
        assert ('merge_patch_list', 'bad_value:' + r) in codes
    for r in ('step.type', 'step.kind', 'missing', 'leaf'):
        assert ('get_path', 'bad_value:path.' + r) in codes
    assert ('get_path', 'bad_type:path') in codes and ('merge_patch_list', 'bad_type:patches') in codes
    for r in ('ok', 'float.nan', 'float.inf', 'key', 'depth', 'nodes', 'type'):
        assert any(f == 'value_reason' and w == r for f, a, w in SUCCESS)


def test_fallback_failer_world_has_no_imports_one_success_and_every_refusal(mp):
    real = builtins.__import__
    seen = []
    name = 'b1177_fallback_world'

    def hook(n, g=None, l=None, fromlist=(), level=0):
        if g is not None and g.get('__name__') == name:
            seen.append((n, tuple(fromlist or ()), level))
        return real(n, g, l, fromlist, level)
    mp.setitem(sys.modules, REG, None)
    mp.setattr(builtins, '__import__', hook)
    mod = fresh(name)
    assert mod.make_fail.__module__ == name
    assert seen == IMPORTS
    del seen[:]
    drive(mod, 'P235:')
    assert seen == []
    with pytest.raises(ValueError) as e:
        mod.make_fail('x')('c')
    assert str(e.value) == 'P235:x:c'
    assert seen == []


def test_every_refusal_goes_through_the_failer_call_site(mp):
    """Stub world: the bound failer raises a sentinel; the last frame inside the module for each refusal is a line starting with fail(."""
    class Stop(Exception):
        pass

    def make(name):
        def fail(code):
            raise Stop(name + ':' + code)
        return fail
    fake = types.ModuleType(REG)
    fake.make_fail = make
    mp.setitem(sys.modules, REG, fake)
    mod = fresh('b1177_site_world')
    sites = set()
    for fn, args, want in CORPUS:
        with pytest.raises(Stop) as e:
            getattr(mod, fn)(*args)
        assert str(e.value) == fn + ':' + want
        frames = [f for f in traceback.extract_tb(e.value.__traceback__) if f.filename == mod.__file__]
        assert frames[-1].line.strip().startswith('fail(')
        sites.add(frames[-1].lineno)
    src = inspect.getsource(mod).split('\n')
    all_sites = {i + 1 for i, line in enumerate(src) if line.strip().startswith('fail(') and 'def ' not in line}
    assert sites == all_sites, sorted(all_sites - sites)


def test_fixture_autouse_hook_is_installed_and_sees_module_names():
    assert getattr(builtins.__import__, '__name__', '') == 'hook'


@pytest.fixture(autouse=True)
def _module_never_imports_at_call_time(monkeypatch):
    """Every test drives the module through the hook: any import executed by the module's own code after load fails the test."""
    real = builtins.__import__
    seen = []

    def hook(n, g=None, l=None, fromlist=(), level=0):
        if g is not None and g.get('__name__') == m.__name__:
            seen.append((n, tuple(fromlist or ()), level))
        return real(n, g, l, fromlist, level)
    monkeypatch.setattr(builtins, '__import__', hook)
    yield
    assert seen == []


def test_fallback_failer_functions_carry_no_docstring(mp):
    mp.setitem(sys.modules, REG, None)
    mod = fresh('b1177_doc_world')
    assert mod.make_fail.__doc__ is None
    assert mod.make_fail('x').__doc__ is None
    assert mod.make_fail.__name__ == 'make_fail' and mod.make_fail('x').__name__ == 'fail'


def test_find_spec_is_consulted_exactly_once_in_the_absent_world_simulation(mp):
    spied = []
    mp.setitem(sys.modules, REG, None)
    mp.setattr(importlib.util, 'find_spec', lambda n: spied.append(n) or None)
    mod = fresh('b1177_spec_world')
    assert spied == [REG] and mod.make_fail.__module__ == mod.__name__


def _world(mp, exc_factory, spec_result, register=None):
    """Run fresh() with __import__ of REG raising exc_factory() (or present as a fake module); return (outcome, spied calls)."""
    real = builtins.__import__
    spied = []
    err = exc_factory() if exc_factory else None

    def hook(n, g=None, l=None, fromlist=(), level=0):
        if n == REG and err is not None:
            raise err
        return real(n, g, l, fromlist, level)

    def spy(name):
        spied.append(name)
        return spec_result
    mp.setitem(sys.modules, REG, register if register is not None else None)
    mp.setattr(importlib.util, 'find_spec', spy)
    mp.setattr(builtins, '__import__', hook)
    try:
        mod = fresh()
    except BaseException as e:
        return ('raised', e, err), spied
    return ('loaded', mod, err), spied


_FAKE = types.ModuleType(REG)
_FAKE.make_fail = lambda name: (lambda code: (_ for _ in ()).throw(ValueError('FAKE:%s:%s' % (name, code))))
GUARD_WORLDS = [
    ('absent', lambda: ModuleNotFoundError('absent', name=REG), None, 'fallback', 1),
    ('foreign_found', lambda: ModuleNotFoundError('inner', name=REG), object(), 'raise', 1),
    ('spec_false', lambda: ModuleNotFoundError('inner', name=REG), False, 'raise', 1),
    ('spec_empty_tuple', lambda: ModuleNotFoundError('inner', name=REG), (), 'raise', 1),
    ('foreign_mnf_name', lambda: ModuleNotFoundError('foreign', name='some.other.module'), None, 'raise', 0),
    ('name_x', lambda: ModuleNotFoundError('x', name='x'), None, 'raise', 0),
    ('name_none', lambda: ModuleNotFoundError('none'), None, 'raise', 0),
    ('name_prefix', lambda: ModuleNotFoundError('prefix', name='app.modules.instinct_doc'), None, 'raise', 0),
    ('name_longer', lambda: ModuleNotFoundError('longer', name=REG + '.sub'), None, 'raise', 0),
    ('name_upper', lambda: ModuleNotFoundError('upper', name=REG.upper()), None, 'raise', 0),
    ('import_error', lambda: ImportError('ie', name=REG), None, 'raise', 0),
    ('named_import_error', lambda: ImportError('ie', name='some.other.module'), None, 'raise', 0),
    ('present', None, None, 'present', 0),
]


@pytest.mark.parametrize('label,factory,spec,outcome,calls', GUARD_WORLDS, ids=[w[0] for w in GUARD_WORLDS])
def test_find_spec_call_count_and_outcome_per_world_is_an_exact_table(mp, label, factory, spec, outcome, calls):
    got, spied = _world(mp, factory, spec, _FAKE if outcome == 'present' else None)
    assert len(spied) == calls and spied == [REG] * calls, label
    if outcome == 'raise':
        assert got[0] == 'raised' and got[1] is got[2], label
    elif outcome == 'fallback':
        assert got[0] == 'loaded' and got[1].make_fail.__module__ == got[1].__name__, label
    else:
        assert got[0] == 'loaded' and got[1].make_fail is _FAKE.make_fail, label


def test_child_process_in_isolated_mode_gives_the_same_answers():
    code = ("import sys; sys.path.insert(0, %r)\n"
            "import app.modules.instinct_doc.p235_concepts_batch1177_jsonmerge as m\n"
            "print(m.merge_patch({'a': 'b'}, {'a': None}), m.type_name([1]), m.get_path({'a': [7]}, ('a', 0)), "
            "m.merge_ops({'e': None}, {'a': 1}), m.diff({'a': 1}, {'a': 2}))\n") % (
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(m.__file__)))),)
    out = subprocess.run([sys.executable, '-I', '-c', code], capture_output=True, text=True, timeout=25)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "{} array 7 (('set', ('a',), 1),) {'a': 2}"
    out = subprocess.run([sys.executable, '-I', '-c', code], capture_output=True, text=True, timeout=25, env={'PYTHONHASHSEED': '7'})
    assert out.stdout.strip() == "{} array 7 (('set', ('a',), 1),) {'a': 2}"
