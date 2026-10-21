"""P235 batch 1235: RFC 7232 (HTTP/1.1 Conditional Requests) Section 2.3 (the ETag
header field and the entity-tag grammar), Section 2.3.2 (the strong and weak comparison
functions), Sections 3.1 and 3.2 (the If-Match and If-None-Match field value grammars),
Section 5 (the general precondition evaluation rule) and Section 6 (the precondition
precedence order), as parsers of the field values, formatters back, the two comparison
functions and the precedence order as pure data.

STATUS OF THE RFC: RFC 7232 (June 2014, Standards Track) is obsoleted by RFC 9110 (HTTP
Semantics, June 2022); the RFC Editor info page read 2026-10-21 lists "Obsoleted by RFC
9110: HTTP Semantics". This unit models the RFC 7232 text as printed; RFC 9110 and every
other RFC are not relied on.
OVERLAP (OURS SCOPE): the unit is the entity-tag grammar, the two precondition list
grammars, the two comparison functions and the precedence data; the date-based
preconditions If-Modified-Since (3.3) and If-Unmodified-Since (3.4) and their HTTP-date
grammar, the If-Range grammar (3.5), Last-Modified (2.2), the weak-versus-strong
validator generation rules (2.1), ETag generation (2.3.1), the choice guidance (2.4),
the 304 and 412 response definitions (4) and the registrations (7) belong to other
units or to none and are not modelled.

QUOTED FROM THE RAW RFC TEXT, read 2026-10-21 from the official plain text file
https://www.rfc-editor.org/rfc/rfc7232.txt as 56696 bytes, sha256
3788e183becfbdaf93121082cd90ac7c1324e871fe425438805942a10207b1b4, 28 page breaks (form feeds), 28 page footer lines ("[Page"). Each of the 11 passages below is
one contiguous run of whole lines of that raw file, copied without elision or change;
the raw line numbers are in each passage title. The rest of the RFC is not quoted and
not modelled.

PASSAGE 1 (RFC 7232 Section 2.3, the ETag and entity-tag grammar, raw lines 477-483)

     ETag       = entity-tag

     entity-tag = [ weak ] opaque-tag
     weak       = %x57.2F ; "W/", case-sensitive
     opaque-tag = DQUOTE *etagc DQUOTE
     etagc      = %x21 / %x23-7E / obs-text
                ; VCHAR except double quotes, plus obs-text

PASSAGE 2 (RFC 7232 Section 2.3.2, the two comparison functions, raw lines 547-552)

   o  Strong comparison: two entity-tags are equivalent if both are not
      weak and their opaque-tags match character-by-character.

   o  Weak comparison: two entity-tags are equivalent if their
      opaque-tags match character-by-character, regardless of either or
      both being tagged as "weak".

PASSAGE 3 (RFC 7232 Section 2.3.2, the comparison example table, raw lines 567-576)

   The example below shows the results for a set of entity-tag pairs and
   both the weak and strong comparison function results:

   +--------+--------+-------------------+-----------------+
   | ETag 1 | ETag 2 | Strong Comparison | Weak Comparison |
   +--------+--------+-------------------+-----------------+
   | W/"1"  | W/"1"  | no match          | match           |
   | W/"1"  | W/"2"  | no match          | no match        |
   | W/"1"  | "1"    | no match          | match           |
   | "1"    | "1"    | match             | match           |

PASSAGE 4 (RFC 7232 Section 3.1, the If-Match comparison rule, grammar and examples, raw lines 709-720)

   An origin server MUST use the strong comparison function when
   comparing entity-tags for If-Match (Section 2.3.2), since the client
   intends this precondition to prevent the method from being applied if
   there have been any changes to the representation data.

     If-Match = "*" / 1#entity-tag

   Examples:

     If-Match: "xyzzy"
     If-Match: "xyzzy", "r2d2xxxx", "c3piozzzz"
     If-Match: *

PASSAGE 5 (RFC 7232 Section 3.1, the If-Match false condition, raw lines 739-745)

   An origin server that receives an If-Match header field MUST evaluate
   the condition prior to performing the method (Section 5).  If the
   field-value is "*", the condition is false if the origin server does
   not have a current representation for the target resource.  If the
   field-value is a list of entity-tags, the condition is false if none
   of the listed tags match the entity-tag of the selected
   representation.

PASSAGE 6 (RFC 7232 Section 3.2, the If-None-Match comparison rule and grammar, raw lines 772-777)

   A recipient MUST use the weak comparison function when comparing
   entity-tags for If-None-Match (Section 2.3.2), since weak entity-tags
   can be used for cache validation even if there have been changes to
   the representation data.

     If-None-Match = "*" / 1#entity-tag

PASSAGE 7 (RFC 7232 Section 3.2, the If-None-Match examples, raw lines 791-797)

   Examples:

     If-None-Match: "xyzzy"
     If-None-Match: W/"xyzzy"
     If-None-Match: "xyzzy", "r2d2xxxx", "c3piozzzz"
     If-None-Match: W/"xyzzy", W/"r2d2xxxx", W/"c3piozzzz"
     If-None-Match: *

PASSAGE 8 (RFC 7232 Section 3.2, the If-None-Match false condition, raw lines 816-828)

   An origin server that receives an If-None-Match header field MUST
   evaluate the condition prior to performing the method (Section 5).
   If the field-value is "*", the condition is false if the origin
   server has a current representation for the target resource.  If the
   field-value is a list of entity-tags, the condition is false if one
   of the listed tags match the entity-tag of the selected
   representation.

   An origin server MUST NOT perform the requested method if the
   condition evaluates to false; instead, the origin server MUST respond
   with either a) the 304 (Not Modified) status code if the request
   method is GET or HEAD or b) the 412 (Precondition Failed) status code
   for all other request methods.

PASSAGE 9 (RFC 7232 Section 5, the general evaluation rule, raw lines 1051-1059)

   Except when excluded below, a recipient cache or origin server MUST
   evaluate received request preconditions after it has successfully
   performed its normal request checks and just before it would perform
   the action associated with the request method.  A server MUST ignore
   all received preconditions if its response to the same request
   without those conditions would have been a status code other than a
   2xx (Successful) or 412 (Precondition Failed).  In other words,
   redirects and failures take precedence over the evaluation of
   preconditions in conditional requests.

PASSAGE 10 (RFC 7232 Section 6, precedence order intro and step 1, raw lines 1108-1118)

   A recipient cache or origin server MUST evaluate the request
   preconditions defined by this specification in the following order:

   1.  When recipient is the origin server and If-Match is present,
       evaluate the If-Match precondition:

       *  if true, continue to step 3

       *  if false, respond 412 (Precondition Failed) unless it can be
          determined that the state-changing request has already
          succeeded (see Section 3.1)

PASSAGE 11 (RFC 7232 Section 6, precedence steps 2 to 6, raw lines 1127-1164)

   2.  When recipient is the origin server, If-Match is not present, and
       If-Unmodified-Since is present, evaluate the If-Unmodified-Since
       precondition:

       *  if true, continue to step 3

       *  if false, respond 412 (Precondition Failed) unless it can be
          determined that the state-changing request has already
          succeeded (see Section 3.4)

   3.  When If-None-Match is present, evaluate the If-None-Match
       precondition:

       *  if true, continue to step 5

       *  if false for GET/HEAD, respond 304 (Not Modified)

       *  if false for other methods, respond 412 (Precondition Failed)

   4.  When the method is GET or HEAD, If-None-Match is not present, and
       If-Modified-Since is present, evaluate the If-Modified-Since
       precondition:

       *  if true, continue to step 5

       *  if false, respond 304 (Not Modified)

   5.  When the method is GET and both Range and If-Range are present,
       evaluate the If-Range precondition:

       *  if the validator matches and the Range specification is
          applicable to the selected representation, respond 206
          (Partial Content) [RFC7233]

   6.  Otherwise,

       *  all conditions are met, so perform the requested action and
          respond according to its success or failure.

ERRATA: the RFC Editor errata index (https://www.rfc-editor.org/errata.json, which now
redirects to the RFC Editor API; read 2026-10-21 through the redirect as 11766165 bytes, sha256
2771053324fcbbc3f775f4b6d7514c204ba1a4c65077c4fa866614d392640c66) holds
these records.
RFC 7232, 2 records:
- ID 5162 (Verified, Editorial, A)
- ID 5236 (Rejected, Technical, Section 2.1)
RFC 9110, 14 records (obsoletes RFC 7232, not relied on):
- ID 7105 (Verified, Editorial, B.1.)
- ID 7107 (Rejected, Technical, Section 6.5.1)
- ID 7109 (Verified, Editorial, Section 15.4.9)
- ID 7138 (Verified, Technical, Section 12.5.1)
- ID 7306 (Verified, Technical, Section 14.1.1)
- ID 7419 (Verified, Technical, Section 8.3.2)
- ID 7530 (Rejected, Editorial, Section 15.5.2.)
- ID 7599 (Rejected, Technical, Section 6.4.1)
- ID 7870 (Rejected, Technical, Section 8.6)
- ID 8138 (Rejected, Technical, Section 15.4)
- ID 8268 (Verified, Editorial, B.2)
- ID 8459 (Rejected, Technical, Section 15)
- ID 9162 (Reported, Technical, Section 5.2)
- ID 9164 (Reported, Technical, Appendix A)
RFC 7232 ID 5162 (Verified, Editorial, A) is on the Appendix A changes entry for the
ETag ABNF (the changes note is incomplete: it omits that the space character is now
disallowed). Appendix A is not quoted or relied on; the grammar this unit models is the
Section 2.3 rule as printed, which already disallows the space, so the verified
correction matches the model (ledgered only). ID 5236 (Rejected, Technical, Section
2.1) is on the weak-validator definition of Section 2.1, which is not quoted; it is
rejected, so the printed text stands (ledgered only). The comparison rules this unit
implements come from Section 2.3.2 as printed, not from Section 2.1. RFC 9110 records
are on the obsoleting text and are ledgered only.

SIDE OF THE LINE: this unit takes one field value as text (a str whose characters stand
for octets, so obs-text is the characters 0x80-0xFF) and returns a tagged tuple, or
takes the tuple and writes the field value back. An entity-tag tree is ("etag", weak,
opaque) with weak a bool and opaque the characters between the quotes. A list tree is
("star",) or ("tags", (etag-tree, ...)) with at least one member. The comparison
functions take two entity-tag trees and return a bool. precedence() returns the Section
6 order as data and decides nothing: which preconditions a request carries, what the
selected representation is, whether its tag matches, and what a server does with the
outcome are all outside. A refusal is a ValueError whose code is "bad_type:<where>" or
"bad_value:<where>".

SOURCED FROM THE PASSAGES ABOVE: entity-tag = [ weak ] opaque-tag; weak = %x57.2F, the
two characters "W/", case-sensitive; opaque-tag = DQUOTE *etagc DQUOTE with etagc = %x21
/ %x23-7E / obs-text, that is VCHAR except the double quote, plus obs-text, so the space
and every control are outside; strong comparison: two entity-tags are equivalent if both
are not weak and their opaque-tags match character-by-character; weak comparison: the
opaque-tags match character-by-character regardless of either or both being weak; the
example table gives W/"1" vs W/"1" = no match strong / match weak, W/"1" vs W/"2" = no /
no, W/"1" vs "1" = no / match, "1" vs "1" = match / match; an origin server MUST use the
strong comparison function for If-Match; a recipient MUST use the weak comparison
function for If-None-Match; If-Match = "*" / 1#entity-tag; If-None-Match = "*" /
1#entity-tag; the If-Match condition is false if the field-value is "*" and the origin
server has no current representation, or if it is a list and none of the listed tags
match the entity-tag of the selected representation; the If-None-Match false condition
responds 304 for GET or HEAD and 412 for all other methods; received preconditions are
evaluated after the normal request checks and just before the method's action, and are
all ignored when the unconditional response would not be 2xx or 412; the precedence
order is the six steps of Section 6 in order: If-Match (origin server), then
If-Unmodified-Since (origin server, If-Match absent), then If-None-Match, then
If-Modified-Since (GET or HEAD, If-None-Match absent), then If-Range (GET, Range
present), then perform the requested action.

DECISIONS OURS, where the RFC allows a choice or is silent (each pinned by a test):
- The precedence data rows are (step, field, origin_only, requires_absent, methods,
  requires_also_present, false_outcome, true_goto): step int 1-6; field the header field
  name lowercase or None for the final action step; origin_only a bool (steps 1 and 2);
  requires_absent the field that must be missing (step 2: "if-match", step 4:
  "if-none-match") or None; methods the methods the step applies to as a tuple or None
  for any (step 4: ("GET", "HEAD"), step 5: ("GET",)); requires_also_present fields that
  must also be there (step 5: ("range",)) or None; false_outcome a short string
  ("412-unless-already-succeeded" for steps 1 and 2, "304-if-get-or-head-else-412" for
  step 3, "304" for step 4, "206-if-validator-matches-and-range-applicable" for step 5,
  "perform-requested-action" for step 6); true_goto the step a true condition continues
  to (3, 3, 5, 5, 6, 6).
- parse_entity_tag checks, in order: the type of value; its size (at most 8192
  characters); the opening (a "W/" prefix, then a double quote); the characters (each an
  etagc); the closing double quote; and that nothing follows it. A lowercase "w/" prefix
  or a "W/" not followed by a double quote is bad_value:etag.weak; any other start that
  is not a double quote is bad_value:etag.open; a bad character is bad_value:etag.char;
  end of text before the closing quote is bad_value:etag.close; trailing text is
  bad_value:etag.trail. There is no whitespace anywhere inside an entity-tag.
- parse_precondition_list checks, in order: the type of value; its size; the type of
  field; that field is "if-match" or "if-none-match"; then the value. Optional
  whitespace (spaces and tabs) is allowed around the whole value, around each member and
  around the commas (OURS: the #rule of RFC 7230 puts OWS around the comma separators,
  and leading and trailing OWS of a field value carry no meaning). "*" must stand alone:
  anything after it is bad_value:list.star. An empty value is bad_value:list.empty; an
  empty member (a leading comma, two commas, or a trailing comma) is
  bad_value:list.member; a member that is not an entity-tag fails with the entity-tag
  code; text after a member that is not a comma is bad_value:list.sep. There is no
  member-count cap beyond the field cap (OURS).
- format_entity_tag and format_precondition_list check the tree with exact types (a
  bool is not an int; order: the type of the tree, its shape, then each part), refuse a
  result above 8192 characters (bad_value:tree.size), and re-parse their own text: a
  refusal from that parse is passed on (with the name of the function that was called),
  and a tree that does not come back equal is bad_value:tree.mismatch (this catches an
  opaque string with a bad character, and the like). The formatter writes no whitespace
  for "*" and one space after each comma in a list.
- strong_compare and weak_compare check both trees the same way (bad_type:a,
  bad_value:a.shape, bad_value:a.char, then the same for b) and return a plain bool.
- constants() returns {"field_cap": 8192, "precedence_steps": 6}.

NOT MODELLED: see NOT_CLAIMED in the module: the date-based preconditions and the
HTTP-date grammar, If-Range's grammar, Last-Modified, validator generation, the 304/412
response definitions and the registrations.
"""
from importlib.util import find_spec
try:
    from app.modules.instinct_doc.p235_concepts_registry import make_fail
except ModuleNotFoundError as exc:
    if exc.name != 'app.modules.instinct_doc.p235_concepts_registry' or find_spec('app.modules.instinct_doc.p235_concepts_registry') is not None:
        raise

    def make_fail(name):

        def fail(code):
            raise ValueError('P235:%s:%s' % (name, code))
        return fail
FIELD_CAP = 8192
TAG = 'preconditions'
FIELDS = ('if-match', 'if-none-match')
PRECEDENCE = ((1, 'if-match', True, None, None, None, '412-unless-already-succeeded', 3), (2, 'if-unmodified-since', True, 'if-match', None, None, '412-unless-already-succeeded', 3), (3, 'if-none-match', False, None, None, None, '304-if-get-or-head-else-412', 5), (4, 'if-modified-since', False, 'if-none-match', ('GET', 'HEAD'), None, '304', 5), (5, 'if-range', False, None, ('GET',), ('range',), '206-if-validator-matches-and-range-applicable', 6), (6, None, False, None, None, None, 'perform-requested-action', 6))

def constants():
    return {'field_cap': FIELD_CAP, 'precedence_steps': len(PRECEDENCE)}

def precedence():
    return PRECEDENCE

def _etagc(c):
    o = ord(c)
    if 128 <= o <= 255:
        return True
    return 33 <= o <= 126 and c != '"'

def _ows(s, i, n):
    while i < n and (s[i] == ' ' or s[i] == '\t'):
        i += 1
    return i

def _tag(s, i, n, f):
    weak = False
    if i + 1 < n and s[i] == 'W' and (s[i + 1] == '/'):
        weak = True
        i += 2
        if i >= n or s[i] != '"':
            f('bad_value:etag.weak')
    elif i < n and s[i] == 'w' and (i + 1 < n) and (s[i + 1] == '/'):
        f('bad_value:etag.weak')
    elif i >= n or s[i] != '"':
        f('bad_value:etag.open')
    i += 1
    start = i
    while True:
        if i >= n:
            f('bad_value:etag.close')
        c = s[i]
        if c == '"':
            return (weak, s[start:i], i + 1)
        if not _etagc(c):
            f('bad_value:etag.char')
        i += 1

def parse_entity_tag(value):
    f = make_fail('parse_entity_tag')
    if type(value) is not str:
        f('bad_type:value')
    if len(value) > FIELD_CAP:
        f('bad_value:value.size')
    n = len(value)
    weak, opaque, i = _tag(value, 0, n, f)
    if i < n:
        f('bad_value:etag.trail')
    return ('etag', weak, opaque)

def _check_tag(t, w, f):
    if type(t) is not tuple:
        f('bad_type:%s' % w)
    if len(t) != 3 or t[0] != 'etag' or type(t[1]) is not bool or (type(t[2]) is not str):
        f('bad_value:%s.shape' % w)
    for c in t[2]:
        if not _etagc(c):
            f('bad_value:%s.char' % w)

def format_entity_tag(tree):
    f = make_fail('format_entity_tag')
    _check_tag(tree, 'tree', f)
    out = ('W/' if tree[1] else '') + '"' + tree[2] + '"'
    if len(out) > FIELD_CAP:
        f('bad_value:tree.size')
    back = parse_entity_tag(out)
    if back != tree:
        f('bad_value:tree.mismatch')
    return out

def parse_precondition_list(value, field):
    f = make_fail('parse_precondition_list')
    if type(value) is not str:
        f('bad_type:value')
    if len(value) > FIELD_CAP:
        f('bad_value:value.size')
    if type(field) is not str:
        f('bad_type:field')
    if field not in FIELDS:
        f('bad_value:field')
    n = len(value)
    i = _ows(value, 0, n)
    if i >= n:
        f('bad_value:list.empty')
    if value[i] == '*':
        i = _ows(value, i + 1, n)
        if i < n:
            f('bad_value:list.star')
        return ('star',)
    out = []
    while True:
        i = _ows(value, i, n)
        if i >= n or value[i] == ',':
            f('bad_value:list.member')
        weak, opaque, i = _tag(value, i, n, f)
        out.append(('etag', weak, opaque))
        i = _ows(value, i, n)
        if i >= n:
            return ('tags', tuple(out))
        if value[i] != ',':
            f('bad_value:list.sep')
        i += 1

def format_precondition_list(tree, field):
    f = make_fail('format_precondition_list')
    if type(tree) is not tuple:
        f('bad_type:tree')
    if type(field) is not str:
        f('bad_type:field')
    if field not in FIELDS:
        f('bad_value:field')
    if len(tree) == 1 and tree[0] == 'star':
        out = '*'
    elif len(tree) == 2 and tree[0] == 'tags' and (type(tree[1]) is tuple) and (len(tree[1]) > 0):
        parts = []
        for t in tree[1]:
            _check_tag(t, 'tree', f)
            parts.append(('W/' if t[1] else '') + '"' + t[2] + '"')
        out = ', '.join(parts)
    else:
        f('bad_value:tree.shape')
    if len(out) > FIELD_CAP:
        f('bad_value:tree.size')
    back = parse_precondition_list(out, field)
    if back != tree:
        f('bad_value:tree.mismatch')
    return out

def strong_compare(a, b):
    f = make_fail('strong_compare')
    _check_tag(a, 'a', f)
    _check_tag(b, 'b', f)
    return not a[1] and (not b[1]) and (a[2] == b[2])

def weak_compare(a, b):
    f = make_fail('weak_compare')
    _check_tag(a, 'a', f)
    _check_tag(b, 'b', f)
    return a[2] == b[2]
SCOPE = 'PARTIAL: RFC 7232 (HTTP/1.1 Conditional Requests): the entity-tag grammar (2.3), the two entity-tag comparison functions (2.3.2), the If-Match (3.1) and If-None-Match (3.2) field value grammars, the general precondition evaluation rule (5) and the precondition precedence order (6) as pure data.'
NOT_CLAIMED = 'If-Modified-Since (3.3), If-Unmodified-Since (3.4) and If-Range (3.5) field value grammars and the HTTP-date grammar they use; Last-Modified (2.2) generation and comparison; the 304 (4.1) and 412 (4.2) response definitions; weak versus strong validator generation rules (2.1); when to send which validator (2.4); ETag generation (2.3.1); the content-negotiation example (2.3.3); status code and header field registrations (7); security considerations (8).'
ADJACENT = 'RFC 7233 (Range requests): the If-Range and Range evaluation of precedence step 5; RFC 7231 (moved to RFC 9110): method definitions and content negotiation; RFC 7234 (obsoleted by RFC 9111): cache freshness and validation that consume these preconditions.'
