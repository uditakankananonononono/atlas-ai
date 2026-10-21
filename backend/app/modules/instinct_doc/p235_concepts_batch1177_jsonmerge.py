r"""p235 concepts batch 1177 (rev 0): RFC 7396 JSON Merge Patch processing over decoded caller-supplied values. Pure functions over caller-supplied data. No retrieval, no network, no clock. This unit never parses or serializes JSON text: inputs are decoded Python values only. Every claim in CLAIMS is asserted False: this module is not the standard, not an authority, not certified, not current, not complete; it performs no HTTP PATCH negotiation, registers no media type and makes no authorization decision. ADJACENT names the neighbouring units this unit deliberately does not implement: the RFC 8259 sections 2-7 JSON text grammar (b1214), the RFC 7464 JSON text sequence framing (b1176), and RFC 6902 JSON Patch with RFC 6901 JSON Pointer (b1178).

LIVE-READ SOURCES (read live, quoted verbatim below and mechanically matched against the whitespace-collapsed RFC text with the page headers and footers removed):
- RFC 7396, JSON Merge Patch, Standards Track, October 2014, Hoffman & Snell. rfc7396.txt is 12791 bytes, sha256 545e1d61667c243ea14d6b1a56212370a26d46e1acd441803805fcdecd9164c6.
- RFC 8259, The JavaScript Object Notation (JSON) Data Interchange Format, Standards Track, December 2017, for the value data model the decoded values follow. rfc8259.txt is 28360 bytes, sha256 61a5378f4255c720beb2a4b4a63b29540147c140f36988bf086291989b4cd2d7.
- RFC 7159, March 2014, because 7396's own normative reference is 7159 (section 6.1). rfc7159.txt is 27451 bytes, sha256 50aa72534210945457f5460a50f263c1d6cf87a3da8c814c1d9f54cb04f22342. The rfc-editor info page for RFC 7159 shows Obsoleted by RFC 8259; the value definition cited here is the same text in both documents.
- The rfc-editor info page for RFC 7396 lists Obsoletes (1): RFC 7386, and shows no Obsoleted by entry and no Updated by entry: RFC 7396 is the current JSON Merge Patch document. The info page for RFC 8259 likewise shows no Obsoleted by entry. CLAIMS current is still False.
- errata.json (sha256 2771053324fcbbc3f775f4b6d7514c204ba1a4c65077c4fa866614d392640c66) records 0 errata for RFC 7396. It records 16 errata for RFC 8259: 5218 (Rejected, Technical, section 12), 5853 (Rejected, Technical, section 11), 7600 (Verified, Technical, section 6), 7603 (Verified, Technical, section 1), 7617 (Rejected, Technical, section 6), 6208 (Rejected, Technical, section 8.1), 7307 (Rejected, Technical, section 3), 7383 (Verified, Technical, section 3), 8874 (Rejected, Technical, section 6), 7650 (Held for Document Update, Technical, section 7), 8438 (Held for Document Update, Editorial, section 14.1), 7673 (Rejected, Technical, section 7), 5210 (Verified, Editorial, GLOBAL), 8622 (Rejected, Technical, section 4), 5318 (Verified, Editorial, section 7) and 9095 (Reported, Technical, section 11). Two touch the section 3 value definition cited here, and their pages were read directly: 7383 (Verified, Technical, section 3) corrects the capitalization of hex literals in the false/null ABNF, a text-grammar detail that changes no decoded value, and 7307 (Rejected, Technical, section 3) was rejected, the verifier noting the original specification is clear. RFC 7159 carries 9 errata in the same index: 3915 (Verified, Technical, section 12), 3984 (Rejected, Technical, section 7), 3983 (Rejected, Technical, section 2), 4220 (Rejected, Technical, section 7), 4264 (Verified, Editorial, section 15.2), 4298 (Rejected, Technical, section 7), 4336 (Verified, Editorial, Appendix A), 4388 (Held for Document Update, Editorial, section 1.2) and 8437 (Rejected, Technical, section 4); none touches the section 3 value definition used here. RFC 7386, the obsoleted predecessor, carries 1 erratum: 4132 (Verified, Technical, section 2). The counts are taken from that single JSON index and are not independently confirmed against the per-erratum pages. OURS: no erratum is applied. The RFC texts decide.

SOURCED (the RFC text):
- The algorithm (7396 section 2): "define MergePatch(Target, Patch): if Patch is an Object: if Target is not an Object: Target = {} # Ignore the contents and set it to an empty Object for each Name/Value pair in Patch: if Value is null: if Name exists in Target: remove the Name/Value pair from Target else: Target[Name] = MergePatch(Target[Name], Value) return Target else: return Patch"
- Arguments (section 2): "The Target argument can be any JSON value or undefined. The Patch argument can be any JSON value."
- Whole replacement (section 2): "If the patch is anything other than an object, the result will always be to replace the entire target with the entire patch."
- No partial patch of a non-object (section 2): "Also, it is not possible to patch part of a target that is not an object, such as to replace just some of the values in an array."
- Data items, not text (section 2): "The MergePatch operation is defined to operate at the level of data items, not at the level of textual representation." "There is no expectation that the MergePatch operation will preserve features at the textual-representation level such as white space, member ordering, number precision beyond what is available in the target's implementation, and so forth."
- Duplicate names (section 2): "In addition, even if the target implementation allows multiple name/value pairs with the same name, the result of the MergePatch operation on such objects is not defined."
- Null removes (section 1): "Null values in the merge patch are given special meaning to indicate the removal of existing values in the target."
- Fit (section 1): "This design means that merge patch documents are suitable for describing modifications to JSON documents that primarily use objects for their structure and do not make use of explicit null values. The merge patch format is not appropriate for all JSON syntaxes."
- Media type (section 4): "Subtype name: merge-patch+json"
- Normative reference (section 6.1): "Bray, T., "The JavaScript Object Notation (JSON) Data Interchange Format", RFC 7159, March 2014,"
- The value model (RFC 8259 section 3): "A JSON value MUST be an object, array, number, or string, or one of the following three literal names: false null true" "value = false / null / true / object / array / number / string"
- Objects (8259 section 4): "An object structure is represented as a pair of curly brackets surrounding zero or more name/value pairs (or members). A name is a string." "The names within an object SHOULD be unique."
- Arrays (8259 section 5): "An array structure is represented as square brackets surrounding zero or more values (or elements). Elements are separated by commas." "There is no requirement that the values in an array be of the same type."
- Numbers (8259 section 6): "Numeric values that cannot be represented in the grammar below (such as Infinity and NaN) are not permitted."

OURS (conventions this module adds, each pinned by tests):
1. Decoded values only. Inputs are Python values, never JSON text; parsing and serializing text belongs to the adjacent grammar units. The mapping uses exact built-in types by identity: dict is object, list is array, str is string, int and float are number, bool is the true and false literals, None is null. Subclasses of any of these are refused as type. A hostile __eq__, __hash__ or metaclass is never consulted: validation uses type identity and membership only.
2. Numbers. int of any size and finite float are numbers. NaN and the two infinities are refused (float.nan, float.inf): 8259 section 6 does not permit them.
3. No mutation, fresh results. merge_patch, merge_patch_list, canonical and diff return freshly built dict and list structures, and the set values inside merge_ops are fresh; inputs are never mutated and results share no mutable structure with any input. get_path is the exception: it returns the found value itself, not a copy.
4. Member order. Patch members are visited in dict insertion order, matching "for each Name/Value pair in Patch"; merge_ops, removed_paths and the diff member order follow the same rule. merge_equal ignores member order, since an object is an unordered collection of name/value pairs (8259 section 4). canonical sorts members by Unicode code point (plain str order).
5. Numeric equality. merge_equal compares int and float by value, so 1 equals 1.0 and -0.0 equals 0.0; a bool is never equal to a number: True does not equal 1; likewise False does not equal 0. Every other type pair compares strictly.
6. Patch nulls remove, target nulls are data. A null member in the patch removes the target member when it exists and is a no-op otherwise; null values already in the target survive untouched, as in the Appendix A case {"e":null} patched by {"a":1} giving {"e":null,"a":1}.
7. Absent members and nested nulls. MergePatch(Target[Name], Value) with Name absent is MergePatch(undefined, Value), and undefined is not an object, so a fresh empty object is used; a null member inside an added object subtree therefore vanishes, exactly as the last Appendix A case shows: {} patched by {"a":{"bb":{"ccc":null}}} gives {"a":{"bb":{}}}. This module passes None for absent members; null and undefined behave identically under the pseudocode's "is not an Object" test.
8. diff (no RFC basis; the RFC defines only application). diff(original, modified) returns {} when original and modified are equal objects; equal non-object values yield a deep copy of modified instead, because any object patch, even an empty one, discards a non-object target and rebuilds it as an object (section 2). When both are objects and differ, it emits, in modified member order, a deep copy of each added member value and a recursive diff of each changed member, then, in original member order, None for each removed member; otherwise a deep copy of modified. The known limit, pinned by tests: an object member whose modified value is null cannot be expressed (null removes), and a null member inside an added object subtree vanishes on application (OURS 7), so merge_patch(original, diff(original, modified)) reproduces modified exactly unless such null members exist, and then differs only at them.
9. merge_ops op shapes: ('set', path, value) and ('remove', path), with path a tuple of member names from the root and () naming the whole value. A non-object patch is the single op ('set', (), copy-of-patch). When the patch member is an object and the target member is an object, the list recurses; every other changed member is one set op whose value is the result the pseudocode would assign there, so an added object already has its null members removed (OURS 7).
10. get_path addressing (no RFC basis): the path is a tuple of exact str steps (object members) or exact int steps (array indices). bool steps are step.type, never indices. Negative indices are path.missing, not Python-style wraparound.

CAPS AND CLOSURE: DEPTH_CAP is 32 container nestings and NODE_CAP is 4096 counted values for every value input; every value, container or scalar, counts once, and object names are not counted. merge_patch_list refuses more than NODE_CAP patches and get_path refuses a path longer than NODE_CAP steps; both lengths are checked before any content is read. Every result is built from nodes of the inputs and is never larger than the inputs that built it: merge_patch and merge_patch_list results are bounded by the target plus the patches, diff by the original plus the modified, and canonical, removed_paths and the merge_ops op values by their own input.

FUNCTIONS, in this order: value_reason, type_name, canonical, merge_equal, merge_patch, merge_patch_list, merge_ops, removed_paths, diff, get_path. Errors are ValueError with the text P235:<function>:<code>. A code is bad_type:<name> (exact built-in type by identity; subclasses and bool-for-int refused) for the non-value arguments, bad_value:<name>.length, or bad_value:<name>.<reason>.

REASONS, in check order (the first failure decides):
- value_reason: never raises; it classifies any object. 'ok' or the first fault of a single preorder traversal (an object's names are checked first, in insertion order, then its children in insertion order; array items in index order): depth (a container nested deeper than DEPTH_CAP), then nodes (the running count crossing NODE_CAP at that value), then type (not an exact dict, list, str, int, float, bool or None), then key (an object name that is not an exact str), then float.nan, then float.inf.
- type_name and canonical: bad_value:value.<the value_reason fault>.
- merge_equal: bad_value:a.<fault>, then bad_value:b.<fault>.
- merge_patch and merge_ops: bad_value:target.<fault>, then bad_value:patch.<fault>.
- merge_patch_list: bad_value:target.<fault>, then bad_type:patches, bad_value:patches.length, then bad_value:patches.item.<fault> for the first faulty patch in list order.
- removed_paths: bad_value:patch.<fault>.
- diff: bad_value:original.<fault>, then bad_value:modified.<fault>.
- get_path: bad_value:value.<fault>, then bad_type:path, bad_value:path.length, then per step in path order bad_value:path.step.type (a step that is not an exact str or exact int; bool is refused here), then while walking: step.kind (an int step at an object or a str step at an array), path.missing (an absent name or an index outside 0..len-1; negative indices are missing), path.leaf (a step remains at a scalar).

OUTPUT ORDER: type_name returns the 8259 section 3 name: 'object', 'array', 'string', 'number', 'true', 'false' or 'null'. canonical returns the value with every object's members sorted by Unicode code point, recursively; array order is kept. merge_patch and merge_patch_list return the merged value: surviving target members keep their position, and members added by the patch are appended in patch visit order. merge_ops returns a tuple of ops in the pseudocode's visit order. removed_paths returns a tuple of name-path tuples in preorder, insertion order. diff returns a patch value whose members are ordered as OURS 8 states. get_path returns the found value itself, not a copy.
"""
SCOPE = 'RFC 7396 JSON Merge Patch processing (section 2) over decoded caller-supplied values: validity, canonical form, equality, single and sequenced application, operation lists, removal paths, patch difference and path lookup'
NOT_CLAIMED = ('standard', 'authority', 'certification', 'currency', 'completeness', 'text-grammar', 'http-patch-semantics', 'media-type-registration', 'authorization')
CLAIMS = {'standard': False, 'authoritative': False, 'certified': False, 'current': False, 'complete': False,
          'text_grammar': False, 'http_patch_semantics': False, 'media_type_registration': False, 'authorization': False}
ADJACENT = ('RFC 8259 sections 2-7 JSON text grammar: parsing and serializing JSON text (b1214)',
            'RFC 7464 JSON text sequences framing over the JSON grammar (b1176)',
            'RFC 6902 JSON Patch operations and RFC 6901 JSON Pointer syntax (b1178)')
DEPTH_CAP = 32
NODE_CAP = 4096
_INF = float('inf')
_NINF = -_INF
from importlib.util import find_spec
_REG = 'app.modules.instinct_doc.p235_concepts_registry'
try:
    from app.modules.instinct_doc.p235_concepts_registry import make_fail
except ModuleNotFoundError as exc:
    if exc.name != _REG or find_spec(_REG) is not None:
        raise
    def make_fail(name):
        def fail(code):
            raise ValueError('P235:%s:%s' % (name, code))
        return fail


def _scan(v):
    # Single preorder pass over a candidate JSON value. Returns 'ok' or the
    # first fault: depth, nodes, type, key, float.nan, float.inf.
    count = 0
    stack = [(v, 1)]
    for _steps in range(NODE_CAP + 8):
        if not stack:
            return 'ok'
        cur, d = stack.pop()
        tc = type(cur)
        is_c = tc is dict or tc is list
        if is_c and d > DEPTH_CAP:
            return 'depth'
        count += 1
        if count > NODE_CAP:
            return 'nodes'
        if tc is dict:
            kids = []
            for k in cur:
                if type(k) is not str:
                    return 'key'
                kids.append(cur[k])
            for i in range(len(kids) - 1, -1, -1):
                kc = kids[i]
                tk = type(kc)
                stack.append((kc, d + 1 if tk is dict or tk is list else d))
        elif tc is list:
            for i in range(len(cur) - 1, -1, -1):
                kc = cur[i]
                tk = type(kc)
                stack.append((kc, d + 1 if tk is dict or tk is list else d))
        elif tc is str or tc is bool or tc is int or cur is None:
            pass
        elif tc is float:
            if cur != cur:
                return 'float.nan'
            if cur == _INF or cur == _NINF:
                return 'float.inf'
        else:
            return 'type'
    return 'ok'


def _check(fail, v, name):
    r = _scan(v)
    if r != 'ok':
        fail('bad_value:%s.%s' % (name, r))


def _copy(v):
    t = type(v)
    if t is dict:
        out = {}
        for k in v:
            out[k] = _copy(v[k])
        return out
    if t is list:
        out = []
        for x in v:
            out.append(_copy(x))
        return out
    return v


def _canon(v):
    t = type(v)
    if t is dict:
        keys = []
        for k in v:
            keys.append(k)
        keys.sort()
        out = {}
        for k in keys:
            out[k] = _canon(v[k])
        return out
    if t is list:
        out = []
        for x in v:
            out.append(_canon(x))
        return out
    return v


def _eq(a, b):
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
            if k not in b:
                return False
            if not _eq(a[k], b[k]):
                return False
        return True
    if ta is list:
        if len(a) != len(b):
            return False
        for i in range(len(a)):
            if not _eq(a[i], b[i]):
                return False
        return True
    return a == b


def _merge(t, p):
    # The section 2 pseudocode, building fresh objects. Absent target
    # members arrive as None; null and undefined behave identically under
    # the pseudocode's "is not an Object" test.
    if type(p) is dict:
        if type(t) is dict:
            out = _copy(t)
        else:
            out = {}
        for k in p:
            pv = p[k]
            if pv is None:
                if k in out:
                    del out[k]
            elif k in out:
                out[k] = _merge(out[k], pv)
            else:
                out[k] = _merge(None, pv)
        return out
    return _copy(p)


def _ops(t, p, path):
    out = []
    if type(p) is dict:
        base = t if type(t) is dict else {}
        for k in p:
            pv = p[k]
            kp = path + (k,)
            if pv is None:
                if k in base:
                    out.append(('remove', kp))
            else:
                bv = base[k] if k in base else None
                if type(pv) is dict and type(bv) is dict:
                    for op in _ops(bv, pv, kp):
                        out.append(op)
                else:
                    out.append(('set', kp, _merge(bv, pv)))
        return out
    out.append(('set', path, _copy(p)))
    return out


def _removals(p, path):
    out = []
    if type(p) is dict:
        for k in p:
            pv = p[k]
            if pv is None:
                out.append(path + (k,))
            elif type(pv) is dict:
                for rp in _removals(pv, path + (k,)):
                    out.append(rp)
    return out


def _diff(o, n):
    if _eq(o, n):
        if type(o) is dict and type(n) is dict:
            return {}
        return _copy(n)
    if type(o) is dict and type(n) is dict:
        out = {}
        for k in n:
            if k in o:
                if not _eq(o[k], n[k]):
                    out[k] = _diff(o[k], n[k])
            else:
                out[k] = _copy(n[k])
        for k in o:
            if k not in n:
                out[k] = None
        return out
    return _copy(n)


def value_reason(value):
    return _scan(value)


def type_name(value):
    fail = make_fail('type_name')
    _check(fail, value, 'value')
    t = type(value)
    if t is dict:
        return 'object'
    if t is list:
        return 'array'
    if t is str:
        return 'string'
    if t is bool:
        if value:
            return 'true'
        return 'false'
    if value is None:
        return 'null'
    return 'number'


def canonical(value):
    fail = make_fail('canonical')
    _check(fail, value, 'value')
    return _canon(value)


def merge_equal(a, b):
    fail = make_fail('merge_equal')
    _check(fail, a, 'a')
    _check(fail, b, 'b')
    return _eq(a, b)


def merge_patch(target, patch):
    fail = make_fail('merge_patch')
    _check(fail, target, 'target')
    _check(fail, patch, 'patch')
    return _merge(target, patch)


def merge_patch_list(target, patches):
    fail = make_fail('merge_patch_list')
    _check(fail, target, 'target')
    if type(patches) is not list:
        fail('bad_type:patches')
    if len(patches) > NODE_CAP:
        fail('bad_value:patches.length')
    for it in patches:
        r = _scan(it)
        if r != 'ok':
            fail('bad_value:patches.item.%s' % r)
    out = _copy(target)
    for it in patches:
        out = _merge(out, it)
    return out


def merge_ops(target, patch):
    fail = make_fail('merge_ops')
    _check(fail, target, 'target')
    _check(fail, patch, 'patch')
    out = []
    for op in _ops(target, patch, ()):
        out.append(op)
    return tuple(out)


def removed_paths(patch):
    fail = make_fail('removed_paths')
    _check(fail, patch, 'patch')
    out = []
    for rp in _removals(patch, ()):
        out.append(rp)
    return tuple(out)


def diff(original, modified):
    fail = make_fail('diff')
    _check(fail, original, 'original')
    _check(fail, modified, 'modified')
    return _diff(original, modified)


def get_path(value, path):
    fail = make_fail('get_path')
    _check(fail, value, 'value')
    if type(path) is not tuple:
        fail('bad_type:path')
    if len(path) > NODE_CAP:
        fail('bad_value:path.length')
    cur = value
    for i in range(len(path)):
        step = path[i]
        ts = type(step)
        if ts is not str and ts is not int:
            fail('bad_value:path.step.type')
        tc = type(cur)
        if tc is dict:
            if ts is not str:
                fail('bad_value:path.step.kind')
            if step not in cur:
                fail('bad_value:path.missing')
            cur = cur[step]
        elif tc is list:
            if ts is not int:
                fail('bad_value:path.step.kind')
            if step < 0 or step >= len(cur):
                fail('bad_value:path.missing')
            cur = cur[step]
        else:
            fail('bad_value:path.leaf')
    return cur
