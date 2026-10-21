import ast
import hashlib
import builtins
import importlib
import importlib.util as iu
import itertools
import json
import pathlib
import random
import re
import signal
import sys
import tracemalloc
import types

import pytest

MOD = 'app.modules.instinct_doc.p235_concepts_batch1235_preconditions'
REG = 'app.modules.instinct_doc.p235_concepts_registry'
m = importlib.import_module(MOD)


def refuse(fn, code, args):
    with pytest.raises(ValueError) as e:
        getattr(m, fn)(*args)
    assert type(e.value) is ValueError
    assert str(e.value).endswith(':%s:%s' % (fn, code)), (fn, code, args, str(e.value))
    assert str(e.value).count(':') >= 3


def code_of(fn, args):
    try:
        getattr(m, fn)(*args)
    except ValueError as e:
        return str(e).split(':', 2)[2]
    return None


class SB(bytes):
    pass


class ST(tuple):
    pass


class SS(str):
    pass


class IS(int):
    pass


class SL(list):
    pass


class SD(dict):
    pass


class EqAll:
    def __eq__(self, other):
        return True

    __hash__ = None


LOOKALIKES = ['\u212a', '\u0131', '\u017f', '\u00aa', '\u00df', '\uff43', '\uff4c', '\u0441', '\u043e', '\u0435', '\u00a0', '\u2003', '\u3000', '\u0661']

_MODULE_DOCSTRING = 'P235 batch 1235: RFC 7232 (HTTP/1.1 Conditional Requests) Section 2.3 (the ETag\nheader field and the entity-tag grammar), Section 2.3.2 (the strong and weak comparison\nfunctions), Sections 3.1 and 3.2 (the If-Match and If-None-Match field value grammars),\nSection 5 (the general precondition evaluation rule) and Section 6 (the precondition\nprecedence order), as parsers of the field values, formatters back, the two comparison\nfunctions and the precedence order as pure data.\n\nSTATUS OF THE RFC: RFC 7232 (June 2014, Standards Track) is obsoleted by RFC 9110 (HTTP\nSemantics, June 2022); the RFC Editor info page read 2026-10-21 lists "Obsoleted by RFC\n9110: HTTP Semantics". This unit models the RFC 7232 text as printed; RFC 9110 and every\nother RFC are not relied on.\nOVERLAP (OURS SCOPE): the unit is the entity-tag grammar, the two precondition list\ngrammars, the two comparison functions and the precedence data; the date-based\npreconditions If-Modified-Since (3.3) and If-Unmodified-Since (3.4) and their HTTP-date\ngrammar, the If-Range grammar (3.5), Last-Modified (2.2), the weak-versus-strong\nvalidator generation rules (2.1), ETag generation (2.3.1), the choice guidance (2.4),\nthe 304 and 412 response definitions (4) and the registrations (7) belong to other\nunits or to none and are not modelled.\n\nQUOTED FROM THE RAW RFC TEXT, read 2026-10-21 from the official plain text file\nhttps://www.rfc-editor.org/rfc/rfc7232.txt as 56696 bytes, sha256\n3788e183becfbdaf93121082cd90ac7c1324e871fe425438805942a10207b1b4, 28 page breaks (form feeds), 28 page footer lines ("[Page"). Each of the 11 passages below is\none contiguous run of whole lines of that raw file, copied without elision or change;\nthe raw line numbers are in each passage title. The rest of the RFC is not quoted and\nnot modelled.\n\nPASSAGE 1 (RFC 7232 Section 2.3, the ETag and entity-tag grammar, raw lines 477-483)\n\n     ETag       = entity-tag\n\n     entity-tag = [ weak ] opaque-tag\n     weak       = %x57.2F ; "W/", case-sensitive\n     opaque-tag = DQUOTE *etagc DQUOTE\n     etagc      = %x21 / %x23-7E / obs-text\n                ; VCHAR except double quotes, plus obs-text\n\nPASSAGE 2 (RFC 7232 Section 2.3.2, the two comparison functions, raw lines 547-552)\n\n   o  Strong comparison: two entity-tags are equivalent if both are not\n      weak and their opaque-tags match character-by-character.\n\n   o  Weak comparison: two entity-tags are equivalent if their\n      opaque-tags match character-by-character, regardless of either or\n      both being tagged as "weak".\n\nPASSAGE 3 (RFC 7232 Section 2.3.2, the comparison example table, raw lines 567-576)\n\n   The example below shows the results for a set of entity-tag pairs and\n   both the weak and strong comparison function results:\n\n   +--------+--------+-------------------+-----------------+\n   | ETag 1 | ETag 2 | Strong Comparison | Weak Comparison |\n   +--------+--------+-------------------+-----------------+\n   | W/"1"  | W/"1"  | no match          | match           |\n   | W/"1"  | W/"2"  | no match          | no match        |\n   | W/"1"  | "1"    | no match          | match           |\n   | "1"    | "1"    | match             | match           |\n\nPASSAGE 4 (RFC 7232 Section 3.1, the If-Match comparison rule, grammar and examples, raw lines 709-720)\n\n   An origin server MUST use the strong comparison function when\n   comparing entity-tags for If-Match (Section 2.3.2), since the client\n   intends this precondition to prevent the method from being applied if\n   there have been any changes to the representation data.\n\n     If-Match = "*" / 1#entity-tag\n\n   Examples:\n\n     If-Match: "xyzzy"\n     If-Match: "xyzzy", "r2d2xxxx", "c3piozzzz"\n     If-Match: *\n\nPASSAGE 5 (RFC 7232 Section 3.1, the If-Match false condition, raw lines 739-745)\n\n   An origin server that receives an If-Match header field MUST evaluate\n   the condition prior to performing the method (Section 5).  If the\n   field-value is "*", the condition is false if the origin server does\n   not have a current representation for the target resource.  If the\n   field-value is a list of entity-tags, the condition is false if none\n   of the listed tags match the entity-tag of the selected\n   representation.\n\nPASSAGE 6 (RFC 7232 Section 3.2, the If-None-Match comparison rule and grammar, raw lines 772-777)\n\n   A recipient MUST use the weak comparison function when comparing\n   entity-tags for If-None-Match (Section 2.3.2), since weak entity-tags\n   can be used for cache validation even if there have been changes to\n   the representation data.\n\n     If-None-Match = "*" / 1#entity-tag\n\nPASSAGE 7 (RFC 7232 Section 3.2, the If-None-Match examples, raw lines 791-797)\n\n   Examples:\n\n     If-None-Match: "xyzzy"\n     If-None-Match: W/"xyzzy"\n     If-None-Match: "xyzzy", "r2d2xxxx", "c3piozzzz"\n     If-None-Match: W/"xyzzy", W/"r2d2xxxx", W/"c3piozzzz"\n     If-None-Match: *\n\nPASSAGE 8 (RFC 7232 Section 3.2, the If-None-Match false condition, raw lines 816-828)\n\n   An origin server that receives an If-None-Match header field MUST\n   evaluate the condition prior to performing the method (Section 5).\n   If the field-value is "*", the condition is false if the origin\n   server has a current representation for the target resource.  If the\n   field-value is a list of entity-tags, the condition is false if one\n   of the listed tags match the entity-tag of the selected\n   representation.\n\n   An origin server MUST NOT perform the requested method if the\n   condition evaluates to false; instead, the origin server MUST respond\n   with either a) the 304 (Not Modified) status code if the request\n   method is GET or HEAD or b) the 412 (Precondition Failed) status code\n   for all other request methods.\n\nPASSAGE 9 (RFC 7232 Section 5, the general evaluation rule, raw lines 1051-1059)\n\n   Except when excluded below, a recipient cache or origin server MUST\n   evaluate received request preconditions after it has successfully\n   performed its normal request checks and just before it would perform\n   the action associated with the request method.  A server MUST ignore\n   all received preconditions if its response to the same request\n   without those conditions would have been a status code other than a\n   2xx (Successful) or 412 (Precondition Failed).  In other words,\n   redirects and failures take precedence over the evaluation of\n   preconditions in conditional requests.\n\nPASSAGE 10 (RFC 7232 Section 6, precedence order intro and step 1, raw lines 1108-1118)\n\n   A recipient cache or origin server MUST evaluate the request\n   preconditions defined by this specification in the following order:\n\n   1.  When recipient is the origin server and If-Match is present,\n       evaluate the If-Match precondition:\n\n       *  if true, continue to step 3\n\n       *  if false, respond 412 (Precondition Failed) unless it can be\n          determined that the state-changing request has already\n          succeeded (see Section 3.1)\n\nPASSAGE 11 (RFC 7232 Section 6, precedence steps 2 to 6, raw lines 1127-1164)\n\n   2.  When recipient is the origin server, If-Match is not present, and\n       If-Unmodified-Since is present, evaluate the If-Unmodified-Since\n       precondition:\n\n       *  if true, continue to step 3\n\n       *  if false, respond 412 (Precondition Failed) unless it can be\n          determined that the state-changing request has already\n          succeeded (see Section 3.4)\n\n   3.  When If-None-Match is present, evaluate the If-None-Match\n       precondition:\n\n       *  if true, continue to step 5\n\n       *  if false for GET/HEAD, respond 304 (Not Modified)\n\n       *  if false for other methods, respond 412 (Precondition Failed)\n\n   4.  When the method is GET or HEAD, If-None-Match is not present, and\n       If-Modified-Since is present, evaluate the If-Modified-Since\n       precondition:\n\n       *  if true, continue to step 5\n\n       *  if false, respond 304 (Not Modified)\n\n   5.  When the method is GET and both Range and If-Range are present,\n       evaluate the If-Range precondition:\n\n       *  if the validator matches and the Range specification is\n          applicable to the selected representation, respond 206\n          (Partial Content) [RFC7233]\n\n   6.  Otherwise,\n\n       *  all conditions are met, so perform the requested action and\n          respond according to its success or failure.\n\nERRATA: the RFC Editor errata index (https://www.rfc-editor.org/errata.json, which now\nredirects to the RFC Editor API; read 2026-10-21 through the redirect as 11766165 bytes, sha256\n2771053324fcbbc3f775f4b6d7514c204ba1a4c65077c4fa866614d392640c66) holds\nthese records.\nRFC 7232, 2 records:\n- ID 5162 (Verified, Editorial, A)\n- ID 5236 (Rejected, Technical, Section 2.1)\nRFC 9110, 14 records (obsoletes RFC 7232, not relied on):\n- ID 7105 (Verified, Editorial, B.1.)\n- ID 7107 (Rejected, Technical, Section 6.5.1)\n- ID 7109 (Verified, Editorial, Section 15.4.9)\n- ID 7138 (Verified, Technical, Section 12.5.1)\n- ID 7306 (Verified, Technical, Section 14.1.1)\n- ID 7419 (Verified, Technical, Section 8.3.2)\n- ID 7530 (Rejected, Editorial, Section 15.5.2.)\n- ID 7599 (Rejected, Technical, Section 6.4.1)\n- ID 7870 (Rejected, Technical, Section 8.6)\n- ID 8138 (Rejected, Technical, Section 15.4)\n- ID 8268 (Verified, Editorial, B.2)\n- ID 8459 (Rejected, Technical, Section 15)\n- ID 9162 (Reported, Technical, Section 5.2)\n- ID 9164 (Reported, Technical, Appendix A)\nRFC 7232 ID 5162 (Verified, Editorial, A) is on the Appendix A changes entry for the\nETag ABNF (the changes note is incomplete: it omits that the space character is now\ndisallowed). Appendix A is not quoted or relied on; the grammar this unit models is the\nSection 2.3 rule as printed, which already disallows the space, so the verified\ncorrection matches the model (ledgered only). ID 5236 (Rejected, Technical, Section\n2.1) is on the weak-validator definition of Section 2.1, which is not quoted; it is\nrejected, so the printed text stands (ledgered only). The comparison rules this unit\nimplements come from Section 2.3.2 as printed, not from Section 2.1. RFC 9110 records\nare on the obsoleting text and are ledgered only.\n\nSIDE OF THE LINE: this unit takes one field value as text (a str whose characters stand\nfor octets, so obs-text is the characters 0x80-0xFF) and returns a tagged tuple, or\ntakes the tuple and writes the field value back. An entity-tag tree is ("etag", weak,\nopaque) with weak a bool and opaque the characters between the quotes. A list tree is\n("star",) or ("tags", (etag-tree, ...)) with at least one member. The comparison\nfunctions take two entity-tag trees and return a bool. precedence() returns the Section\n6 order as data and decides nothing: which preconditions a request carries, what the\nselected representation is, whether its tag matches, and what a server does with the\noutcome are all outside. A refusal is a ValueError whose code is "bad_type:<where>" or\n"bad_value:<where>".\n\nSOURCED FROM THE PASSAGES ABOVE: entity-tag = [ weak ] opaque-tag; weak = %x57.2F, the\ntwo characters "W/", case-sensitive; opaque-tag = DQUOTE *etagc DQUOTE with etagc = %x21\n/ %x23-7E / obs-text, that is VCHAR except the double quote, plus obs-text, so the space\nand every control are outside; strong comparison: two entity-tags are equivalent if both\nare not weak and their opaque-tags match character-by-character; weak comparison: the\nopaque-tags match character-by-character regardless of either or both being weak; the\nexample table gives W/"1" vs W/"1" = no match strong / match weak, W/"1" vs W/"2" = no /\nno, W/"1" vs "1" = no / match, "1" vs "1" = match / match; an origin server MUST use the\nstrong comparison function for If-Match; a recipient MUST use the weak comparison\nfunction for If-None-Match; If-Match = "*" / 1#entity-tag; If-None-Match = "*" /\n1#entity-tag; the If-Match condition is false if the field-value is "*" and the origin\nserver has no current representation, or if it is a list and none of the listed tags\nmatch the entity-tag of the selected representation; the If-None-Match false condition\nresponds 304 for GET or HEAD and 412 for all other methods; received preconditions are\nevaluated after the normal request checks and just before the method\'s action, and are\nall ignored when the unconditional response would not be 2xx or 412; the precedence\norder is the six steps of Section 6 in order: If-Match (origin server), then\nIf-Unmodified-Since (origin server, If-Match absent), then If-None-Match, then\nIf-Modified-Since (GET or HEAD, If-None-Match absent), then If-Range (GET, Range\npresent), then perform the requested action.\n\nDECISIONS OURS, where the RFC allows a choice or is silent (each pinned by a test):\n- The precedence data rows are (step, field, origin_only, requires_absent, methods,\n  requires_also_present, false_outcome, true_goto): step int 1-6; field the header field\n  name lowercase or None for the final action step; origin_only a bool (steps 1 and 2);\n  requires_absent the field that must be missing (step 2: "if-match", step 4:\n  "if-none-match") or None; methods the methods the step applies to as a tuple or None\n  for any (step 4: ("GET", "HEAD"), step 5: ("GET",)); requires_also_present fields that\n  must also be there (step 5: ("range",)) or None; false_outcome a short string\n  ("412-unless-already-succeeded" for steps 1 and 2, "304-if-get-or-head-else-412" for\n  step 3, "304" for step 4, "206-if-validator-matches-and-range-applicable" for step 5,\n  "perform-requested-action" for step 6); true_goto the step a true condition continues\n  to (3, 3, 5, 5, 6, 6).\n- parse_entity_tag checks, in order: the type of value; its size (at most 8192\n  characters); the opening (a "W/" prefix, then a double quote); the characters (each an\n  etagc); the closing double quote; and that nothing follows it. A lowercase "w/" prefix\n  or a "W/" not followed by a double quote is bad_value:etag.weak; any other start that\n  is not a double quote is bad_value:etag.open; a bad character is bad_value:etag.char;\n  end of text before the closing quote is bad_value:etag.close; trailing text is\n  bad_value:etag.trail. There is no whitespace anywhere inside an entity-tag.\n- parse_precondition_list checks, in order: the type of value; its size; the type of\n  field; that field is "if-match" or "if-none-match"; then the value. Optional\n  whitespace (spaces and tabs) is allowed around the whole value, around each member and\n  around the commas (OURS: the #rule of RFC 7230 puts OWS around the comma separators,\n  and leading and trailing OWS of a field value carry no meaning). "*" must stand alone:\n  anything after it is bad_value:list.star. An empty value is bad_value:list.empty; an\n  empty member (a leading comma, two commas, or a trailing comma) is\n  bad_value:list.member; a member that is not an entity-tag fails with the entity-tag\n  code; text after a member that is not a comma is bad_value:list.sep. There is no\n  member-count cap beyond the field cap (OURS).\n- format_entity_tag and format_precondition_list check the tree with exact types (a\n  bool is not an int; order: the type of the tree, its shape, then each part), refuse a\n  result above 8192 characters (bad_value:tree.size), and re-parse their own text: a\n  refusal from that parse is passed on (with the name of the function that was called),\n  and a tree that does not come back equal is bad_value:tree.mismatch (this catches an\n  opaque string with a bad character, and the like). The formatter writes no whitespace\n  for "*" and one space after each comma in a list.\n- strong_compare and weak_compare check both trees the same way (bad_type:a,\n  bad_value:a.shape, bad_value:a.char, then the same for b) and return a plain bool.\n- constants() returns {"field_cap": 8192, "precedence_steps": 6}.\n\nNOT MODELLED: see NOT_CLAIMED in the module: the date-based preconditions and the\nHTTP-date grammar, If-Range\'s grammar, Last-Modified, validator generation, the 304/412\nresponse definitions and the registrations.\n'
_SCOPE = 'PARTIAL: RFC 7232 (HTTP/1.1 Conditional Requests): the entity-tag grammar (2.3), the two entity-tag comparison functions (2.3.2), the If-Match (3.1) and If-None-Match (3.2) field value grammars, the general precondition evaluation rule (5) and the precondition precedence order (6) as pure data.'
_NOT_CLAIMED = 'If-Modified-Since (3.3), If-Unmodified-Since (3.4) and If-Range (3.5) field value grammars and the HTTP-date grammar they use; Last-Modified (2.2) generation and comparison; the 304 (4.1) and 412 (4.2) response definitions; weak versus strong validator generation rules (2.1); when to send which validator (2.4); ETag generation (2.3.1); the content-negotiation example (2.3.3); status code and header field registrations (7); security considerations (8).'
_ADJACENT = 'RFC 7233 (Range requests): the If-Range and Range evaluation of precedence step 5; RFC 7231 (moved to RFC 9110): method definitions and content negotiation; RFC 7234 (obsoleted by RFC 9111): cache freshness and validation that consume these preconditions.'
EXPECT_DOC_SHA = 'bd5afe6ca5851efa3c9b4b010d1ef3a5fabb9bc819176fddc595703ceab1d971'
EXPECT_LEDGER = 'RFC 7232, 2 records:\n- ID 5162 (Verified, Editorial, A)\n- ID 5236 (Rejected, Technical, Section 2.1)\nRFC 9110, 14 records (obsoletes RFC 7232, not relied on):\n- ID 7105 (Verified, Editorial, B.1.)\n- ID 7107 (Rejected, Technical, Section 6.5.1)\n- ID 7109 (Verified, Editorial, Section 15.4.9)\n- ID 7138 (Verified, Technical, Section 12.5.1)\n- ID 7306 (Verified, Technical, Section 14.1.1)\n- ID 7419 (Verified, Technical, Section 8.3.2)\n- ID 7530 (Rejected, Editorial, Section 15.5.2.)\n- ID 7599 (Rejected, Technical, Section 6.4.1)\n- ID 7870 (Rejected, Technical, Section 8.6)\n- ID 8138 (Rejected, Technical, Section 15.4)\n- ID 8268 (Verified, Editorial, B.2)\n- ID 8459 (Rejected, Technical, Section 15)\n- ID 9162 (Reported, Technical, Section 5.2)\n- ID 9164 (Reported, Technical, Appendix A)\n'
EXPECT_NREFUSALS = 247
EXPECT_NSUCCESSES = 53
import signal
def _boom(n, f):
    raise TimeoutError('P235 b1235 TIMEOUT')
signal.signal(signal.SIGALRM, _boom)


@pytest.fixture(autouse=True)
def _hang_guard():
    old = signal.signal(signal.SIGALRM, _boom)
    signal.alarm(30)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)
PE = 'parse_entity_tag'
FE = 'format_entity_tag'
PL = 'parse_precondition_list'
FL = 'format_precondition_list'
SC = 'strong_compare'
WC = 'weak_compare'
REFUSALS = []
SUCCESSES = []
D = 'bad_value:'
T_ = 'bad_type:'
IM = 'if-match'
IN = 'if-none-match'
T1 = ('etag', False, '1')
W1 = ('etag', True, '1')

# entity-tag: value type then size
for a in (None, b'"a"', SB(b'"a"'), bytearray(b'"a"'), 5, True, (), [], {}, SS('"a"')):
    REFUSALS.append((PE, (a,), T_ + 'value'))
REFUSALS.append((PE, ('"' + 'x' * 8191 + '"',), D + 'value.size'))
REFUSALS.append((PE, ('W/"' + 'x' * 8190 + '"',), D + 'value.size'))
# opening
for v in ('', 'x', 'W', 'x"a"', ' "a"', '\t"a"', '*', 'W ', 'W"a"', '\x80"a"', 'wz', 'w0', '"a"'.replace('"', '＂')):
    REFUSALS.append((PE, (v,), D + 'etag.open'))
# weak prefix case and shape
for v in ('w/"a"', 'w/"1"', 'w/""', 'W/', 'W/a', 'W/ ', 'W/\t"a"', 'W/x', 'W/1', 'W//"a"', 'w/', 'W/w'):
    REFUSALS.append((PE, (v,), D + 'etag.weak'))
# characters
for v in ('"a b"', '"a\tb"', '"a\x7fb"', '"a\x1fb"', '"a\x00b"', '"a\nb"', '"a\rb"', '" a"', '"a "', '"cafĀ"'):
    REFUSALS.append((PE, (v,), D + 'etag.char'))
for lk in LOOKALIKES:
    if ord(lk) <= 0xFF:
        continue
    REFUSALS.append((PE, ('"a%sb"' % lk,), D + 'etag.char'))
# closing quote missing
for v in ('"', '"a', 'W/"', 'W/"abc', '"\x80'):
    REFUSALS.append((PE, (v,), D + 'etag.close'))
# trailing text
for v in ('"a"x', '"a" ', '"a"\t', '"a",', '"a""b"', 'W/"a" x', '"a"W/', '"a"*'):
    REFUSALS.append((PE, (v,), D + 'etag.trail'))

# format_entity_tag: tree type, shape, chars, size
for t in (None, 'etag', b'', 5, True, [], {}, SS('etag'), ST(('etag', False, 'a')), IS(5)):
    REFUSALS.append((FE, (t,), T_ + 'tree'))
for t in ((), ('etag',), ('etag', True), ('etag', True, 'a', 'x'), ('etags', False, 'a'), ('etag', 1, 'a'), ('etag', None, 'a'),
          ('etag', True, 5), ('etag', True, b'a'), ('etag', True, None), ('etag', True, SS('a')), ('Etag', False, 'a'), ('etag ', False, 'a')):
    REFUSALS.append((FE, (t,), D + 'tree.shape'))
for t in (('etag', False, 'a b'), ('etag', False, 'a"b'), ('etag', False, '\x7f'), ('etag', True, 'Ā'), ('etag', False, 'a\tb')):
    REFUSALS.append((FE, (t,), D + 'tree.char'))
REFUSALS.append((FE, (('etag', False, 'x' * 8191),), D + 'tree.size'))

# precondition list: value type/size, field type/value
for a in ((None, IM), (b'*', IM), (5, IM), (SB(b'*'), IM), (SS('*'), IM), ((), IM)):
    REFUSALS.append((PL, a, T_ + 'value'))
REFUSALS.append((PL, ('"' + 'x' * 8191 + '"', IM), D + 'value.size'))
for a in (('*', None), ('*', 5), ('*', b'if-match'), ('*', SB(b'if-match')), ('*', SS('if-match')), ('*', ())):
    REFUSALS.append((PL, a, T_ + 'field'))
for a in (('*', 'if-range'), ('*', 'IF-MATCH'), ('*', ''), ('*', ' if-match'), ('*', 'if-match '), ('*', 'If-Match'), ('*', 'if-none-match\x00')):
    REFUSALS.append((PL, a, D + 'field'))
# empty / star / members / separators
for v in ('', '   ', '\t'):
    REFUSALS.append((PL, (v, IM), D + 'list.empty'))
for v in ('*x', '* "a"', '**', '*,', '* ,', '*\x80', '*\t"a"', '* w/"a"'):
    REFUSALS.append((PL, (v, IM), D + 'list.star'))
for v in (',"a"', '"a",,"b"', '"a",', '"a" , ', ',', '"a",\t,"b"', ', ', '"a", '):
    REFUSALS.append((PL, (v, IM), D + 'list.member'))
for v in ('"a" "b"', '"a";', '"a"x', '"a"*"b"', '"a"/"b"', '"a" w/"b"'):
    REFUSALS.append((PL, (v, IM), D + 'list.sep'))
# member tag errors carry the list function name
for v, c in (('w/"a"', 'etag.weak'), ('"a b"', 'etag.char'), ('"a', 'etag.close'), ('x', 'etag.open'), ('"a","b"x', 'list.sep'),
             ('"a", w/"b"', 'etag.weak'), ('"Ā"', 'etag.char'), ('"a",', 'list.member')):
    REFUSALS.append((PL, (v, IM), D + c))
    REFUSALS.append((PL, (v, IN), D + c))

# format_precondition_list
for a in ((None, IM), ('star', IM), (5, IM), (ST(('star',)), IM)):
    REFUSALS.append((FL, a, T_ + 'tree'))
REFUSALS.append((FL, (None, None), T_ + 'tree'))
for a in ((('star',), None), (('star',), 5), (('star',), SB(b'if-match')), (('star',), SS('if-match'))):
    REFUSALS.append((FL, a, T_ + 'field'))
for a in ((('star',), 'etag'), (('star',), 'IF-MATCH'), (('star',), '')):
    REFUSALS.append((FL, a, D + 'field'))
for t in ((), ('star', 'x'), ('tags',), ('tags', ()), ('tags', []), ('tags', 'x'), ('x',), ('starx',)):
    REFUSALS.append((FL, (t, IM), D + 'tree.shape'))
REFUSALS.append((FL, (('bogus', (T1,)), IM), D + 'tree.shape'))
# A43 rev1: OWS is SP and HTAB only; no other whitespace is skipped
for _w in ('\n', '\r', '\x0b', '\x0c'):
    REFUSALS.append((PL, ('"a",%s"b"' % _w, IM), D + 'etag.open'))
    REFUSALS.append((PL, (_w + '*', IM), D + 'etag.open'))
    REFUSALS.append((PL, (_w, IM), D + 'etag.open'))
    REFUSALS.append((PL, ('"a"%s' % _w, IM), D + 'list.sep'))
    REFUSALS.append((PL, ('*%s' % _w, IM), D + 'list.star'))
    REFUSALS.append((PL, (_w + '"a"', IM), D + 'etag.open'))
# A43 rev1: the members container must be an exact tuple, not a list
REFUSALS.append((FL, (('tags', [('etag', False, 'a')]), IM), D + 'tree.shape'))
REFUSALS.append((FL, (('tags', (('etag', 1, 'a'),)), IM), D + 'tree.shape'))
REFUSALS.append((FL, (('tags', (('etag', False),)), IM), D + 'tree.shape'))
REFUSALS.append((FL, (('tags', (T1, 'x')), IM), T_ + 'tree'))
REFUSALS.append((FL, (('tags', (None,)), IM), T_ + 'tree'))
REFUSALS.append((FL, (('tags', (('etag', False, 'a b'),)), IM), D + 'tree.char'))
REFUSALS.append((FL, (('tags', (('etag', False, 'x' * 4093), ('etag', True, 'y' * 4093))), IM), D + 'tree.size'))

# comparisons: tree a then tree b
for fn in (SC, WC):
    for a in ((None, T1), ('etag', T1), (5, T1), (ST(T1), T1)):
        REFUSALS.append((fn, a, T_ + 'a'))
    for a in ((('etag', True), T1), (('etag', 1, 'a'), T1), (('etag', True, 5), T1), ((), T1)):
        REFUSALS.append((fn, a, D + 'a.shape'))
    REFUSALS.append((fn, (('etag', False, 'a b'), T1), D + 'a.char'))
    for a in ((T1, None), (T1, 'etag'), (T1, ST(T1))):
        REFUSALS.append((fn, a, T_ + 'b'))
    for a in ((T1, ('etag', True)), (T1, ('etag', 1, 'a'))):
        REFUSALS.append((fn, a, D + 'b.shape'))
    REFUSALS.append((fn, (T1, ('etag', False, 'a b')), D + 'b.char'))
    # both bad: a is checked first
    REFUSALS.append((fn, (None, None), T_ + 'a'))
    REFUSALS.append((fn, (('etag', True), None), D + 'a.shape'))

# successes
for v in ('"wz"', '"w0"', '"xyzzy"', 'W/"xyzzy"', '""', 'W/""', '"!#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~"', '"\x80\xff\xe9"', '"a\\b"',
          '"' + 'x' * 8190 + '"', '"r2d2xxxx"', '"c3piozzzz"', 'W/"' + 'x' * 8188 + '"'):
    SUCCESSES.append((PE, (v,)))
SUCCESSES.append((PL, ('"' + 'x' * 8190 + '"', IM)))
for v in ('*', ' * ', '\t*\t', '"a"', '"a", "b"', '"a","b"', '"a"\t,\t"b"', 'W/"a", "b", "c"', ' "a" ', '"xyzzy", "r2d2xxxx", "c3piozzzz"',
          'W/"xyzzy", W/"r2d2xxxx", W/"c3piozzzz"', '"a" , "b" , "c"'):
    SUCCESSES.append((PL, (v, IM)))
    SUCCESSES.append((PL, (v, IN)))
for t in (T1, W1, ('etag', False, ''), ('etag', True, ''), ('etag', False, '\x80\xff'), ('etag', True, 'a\\b')):
    SUCCESSES.append((FE, (t,)))
SUCCESSES.append((FL, (('tags', (('etag', False, 'x' * 4089), ('etag', True, 'y' * 4094))), IM)))
for t in ((('star',), IM), (('star',), IN), (('tags', (T1,)), IM), (('tags', (T1, W1, ('etag', False, 'c3piozzzz'))), IN)):
    SUCCESSES.append((FL, t))
for fn in (SC, WC):
    SUCCESSES.append((fn, (T1, T1)))
    SUCCESSES.append((fn, (W1, T1)))


_PUBLIC = {'find_spec', 'make_fail', 'FIELD_CAP', 'TAG', 'FIELDS', 'PRECEDENCE', 'constants', 'precedence',
           '_etagc', '_ows', '_tag', 'parse_entity_tag', '_check_tag', 'format_entity_tag',
           'parse_precondition_list', 'format_precondition_list', 'strong_compare', 'weak_compare',
           'SCOPE', 'NOT_CLAIMED', 'ADJACENT'}
_LOG = [('importlib.util', ('find_spec',), 0), (REG, ('make_fail',), 0)]


def _hooked_exec(registry_result, find_result):
    src = pathlib.Path(m.__file__).read_text()
    log = []
    asked = []
    real = builtins.__import__
    stub = types.ModuleType(REG)

    def stub_make_fail(name):
        def fail(code):
            raise ValueError('STUB:%s:%s' % (name, code))
        return fail
    stub.make_fail = stub_make_fail
    fake_util = types.SimpleNamespace(find_spec=lambda n: (asked.append(n), find_result)[1])

    def hook(name, globals=None, locals=None, fromlist=(), level=0):
        log.append((name, tuple(fromlist or ()), level))
        if name == REG:
            if isinstance(registry_result, BaseException):
                raise registry_result
            return stub
        if name == 'importlib.util':
            return fake_util
        return real(name, globals, locals, fromlist, level)
    ns = {'__name__': 'p235_exec', '__builtins__': dict(vars(builtins), __import__=hook)}
    exec(compile(src, '<p235>', 'exec'), ns)
    mod = types.ModuleType('p235_exec')
    mod.__dict__.update(ns)
    return mod, log, asked


def _names(mod):
    return {k for k in vars(mod) if not (k.startswith('__') and k.endswith('__'))}


def _drive(mod, log, prefix):
    del log[:]
    for fn, args, code in REFUSALS:
        with pytest.raises(ValueError) as e:
            getattr(mod, fn)(*args)
        assert type(e.value) is ValueError
        assert str(e.value) == '%s:%s:%s' % (prefix, fn, code)
    for fn, args in SUCCESSES:
        getattr(mod, fn)(*args)
    assert mod.constants() == m.constants()
    assert log == []


def _exec_world(exc, spec):
    src = pathlib.Path(m.__file__).read_text()
    log = []
    asked = []
    real = builtins.__import__
    fake_util = types.SimpleNamespace(find_spec=lambda n: (asked.append(n), spec)[1])

    def hook(name, globals=None, locals=None, fromlist=(), level=0):
        log.append((name, tuple(fromlist or ()), level))
        if name == REG:
            raise exc
        if name == 'importlib.util':
            return fake_util
        return real(name, globals, locals, fromlist, level)
    ns = {'__name__': 'p235_exec', '__builtins__': dict(vars(builtins), __import__=hook)}
    return src, ns, log, asked


def test_import_fallback_path_log_namespace_and_prefix():
    mod, log, asked = _hooked_exec(ModuleNotFoundError('x', name=REG), None)
    assert log == _LOG
    assert asked == [REG]
    assert _names(mod) == _PUBLIC
    _drive(mod, log, 'P235')
    assert asked == [REG]


def test_import_present_path_and_drive():
    mod, log, asked = _hooked_exec(None, None)
    assert log == _LOG
    assert asked == []
    assert _names(mod) == _PUBLIC
    _drive(mod, log, 'STUB')
    assert asked == []


def test_import_foreign_and_registry_raise_paths():
    for exc, spec, expect_asked in (
            (ModuleNotFoundError('x', name='some.other.module'), None, []),
            (ModuleNotFoundError('x', name=None), None, []),
            (ModuleNotFoundError('x', name=REG), object(), [REG]),
            (ModuleNotFoundError('x', name=REG + '.sub'), None, []),
            (ModuleNotFoundError('x', name=REG[:-1]), None, [])):
        src, ns, log, asked = _exec_world(exc, spec)
        with pytest.raises(ModuleNotFoundError) as e:
            exec(compile(src, '<p235>', 'exec'), ns)
        assert e.value is exc
        assert log == _LOG
        assert asked == expect_asked


def test_find_spec_call_count_table():
    def mnf(name=REG):
        return ModuleNotFoundError('x', name=name)
    worlds = [
        ('absent', mnf(), None, (1, 'ok')),
        ('foreign_found', mnf(), object(), (1, 'raised')),
        ('foreign_name', mnf('other.mod'), None, (0, 'raised')),
        ('foreign_name_found', mnf('other.mod'), object(), (0, 'raised')),
        ('name_none', ModuleNotFoundError('x'), object(), (0, 'raised')),
        ('name_x', mnf(REG + '.x'), None, (0, 'raised')),
        ('name_prefix', mnf(REG[:-1]), None, (0, 'raised')),
        ('name_upper', mnf(REG.upper()), None, (0, 'raised')),
        ('name_empty', mnf(''), object(), (0, 'raised')),
        ('importerror', ImportError('x', name=REG), None, (0, 'raised')),
        ('runtime_error', RuntimeError('x'), None, (0, 'raised')),
        ('no_args', ModuleNotFoundError(), None, (0, 'raised'))]
    table = {}
    for key, exc, spec, _ in worlds:
        src, ns, log, asked = _exec_world(exc, spec)
        try:
            exec(compile(src, '<p235>', 'exec'), ns)
            outcome = 'ok'
        except (ImportError, RuntimeError) as e:
            assert e is exc
            outcome = 'raised'
        table[key] = (len(asked), outcome)
        assert log == _LOG
    table['present'] = (len(_hooked_exec(None, None)[2]), 'ok')
    want = {k: w for k, _, _, w in worlds}
    want['present'] = (0, 'ok')
    assert len(want) == 13
    assert table == want


def test_import_error_with_registry_name_propagates():
    exc = ImportError('x', name=REG)
    with pytest.raises(ImportError) as e:
        _hooked_exec(exc, None)
    assert e.value is exc and type(e.value) is ImportError


def test_live_namespace():
    assert _names(m) == _PUBLIC


class OErr(Exception):
    pass


def _oetagc(c):
    o = ord(c)
    return 0x80 <= o <= 0xFF or (0x21 <= o <= 0x7E and c != '"')


def _otag(s, i):
    weak = False
    if s[i:i+2] == 'W/':
        weak = True
        i += 2
    if i >= len(s) or s[i] != '"':
        raise OErr('open')
    i += 1
    start = i
    while i < len(s) and s[i] != '"':
        if not _oetagc(s[i]):
            raise OErr('char')
        i += 1
    if i >= len(s):
        raise OErr('close')
    return weak, s[start:i], i + 1


def _oparse(value):
    if '"' not in value and 'W' not in value:
        raise OErr('open')
    weak, opaque, i = _otag(value, 0)
    if i != len(value):
        raise OErr('trail')
    return ('etag', weak, opaque)


def _olist(value):
    i = 0
    n = len(value)
    while i < n and value[i] in ' \t':
        i += 1
    if i < n and value[i] == '*':
        j = i + 1
        while j < n and value[j] in ' \t':
            j += 1
        if j != n:
            raise OErr('star')
        return ('star',)
    out = []
    while True:
        while i < n and value[i] in ' \t':
            i += 1
        if i >= n or value[i] == ',':
            raise OErr('member')
        weak, opaque, i = _otag(value, i)
        out.append(('etag', weak, opaque))
        while i < n and value[i] in ' \t':
            i += 1
        if i >= n:
            return ('tags', tuple(out))
        if value[i] != ',':
            raise OErr('sep')
        i += 1
        while i < n and value[i] in ' \t':
            i += 1
        if i >= n or value[i] == ',':
            raise OErr('member')


def test_module_docstring_and_literals_exact():
    assert hashlib.sha256(m.__doc__.encode('utf-8')).hexdigest() == EXPECT_DOC_SHA
    assert m.SCOPE == _SCOPE and m.NOT_CLAIMED == _NOT_CLAIMED and m.ADJACENT == _ADJACENT
    for fn in ('parse_entity_tag', 'format_entity_tag', 'parse_precondition_list', 'format_precondition_list',
               'strong_compare', 'weak_compare', 'constants', 'precedence'):
        assert getattr(m, fn).__doc__ is None


def test_docstring_header_passages_and_sources():
    d = m.__doc__
    assert 'P235 batch 1235' in d and 'RFC 7232' in d and 'verbatim' not in d
    assert d.count('PASSAGE ') == 11
    import re as _re
    titles = _re.findall(r'PASSAGE (\d+) \(RFC 7232 (.+), raw lines (\d+)-(\d+)\)', d)
    assert [int(t[0]) for t in titles] == list(range(1, 12))
    assert all(int(t[2]) <= int(t[3]) for t in titles)
    for k in range(1, 12):
        marker = 'PASSAGE %d (' % k
        seg = d[d.index(marker):]
        seg = seg[seg.index('\n\n') + 2:]
        enders = [x for x in (seg.find('\nPASSAGE %d (' % (k + 1)) if k < 11 else -1, seg.find('\nERRATA:')) if x >= 0]
        body = seg[:min(enders)].rstrip('\n')
        assert body.strip(), k
        assert '\f' not in body and '[Page' not in body and 'Fielding & Reschke' not in body


def test_errata_ledger_exact():
    assert EXPECT_LEDGER in m.__doc__
    assert '- ID 5162 (Verified, Editorial, A)' in EXPECT_LEDGER
    assert '- ID 5236 (Rejected, Technical, Section 2.1)' in EXPECT_LEDGER
    assert EXPECT_LEDGER.count('\n- ID ') == 16


def test_refusals_and_successes_tables_exact():
    assert len(REFUSALS) == EXPECT_NREFUSALS and len(SUCCESSES) == EXPECT_NSUCCESSES
    seen = set()
    for fn, args, code in REFUSALS:
        refuse(fn, code, args)
        key = (fn, code)
        seen.add(key)
    for fn, args in SUCCESSES:
        getattr(m, fn)(*args)


def test_parse_exact_samples():
    assert m.parse_entity_tag('"xyzzy"') == ('etag', False, 'xyzzy')
    assert m.parse_entity_tag('W/"xyzzy"') == ('etag', True, 'xyzzy')
    assert m.parse_entity_tag('""') == ('etag', False, '')
    assert m.parse_precondition_list('"xyzzy", "r2d2xxxx", "c3piozzzz"', 'if-match') == (
        'tags', (('etag', False, 'xyzzy'), ('etag', False, 'r2d2xxxx'), ('etag', False, 'c3piozzzz')))
    assert m.parse_precondition_list('W/"xyzzy", W/"r2d2xxxx", W/"c3piozzzz"', 'if-none-match') == (
        'tags', (('etag', True, 'xyzzy'), ('etag', True, 'r2d2xxxx'), ('etag', True, 'c3piozzzz')))
    assert m.parse_precondition_list('*', 'if-match') == ('star',)
    assert m.parse_precondition_list(' \t*\t ', 'if-none-match') == ('star',)


def test_parse_exhaustive_short_values_against_oracle():
    alphabet = ['"', 'W', '/', 'a', ' ', ',', '*', '\t', 'w', '\x80', '\x7f', 'x']
    count = 0
    for n in range(0, 5):
        for tup in itertools.product(alphabet, repeat=n):
            v = ''.join(tup)
            try:
                want = _oparse(v)
            except OErr:
                with pytest.raises(ValueError):
                    m.parse_entity_tag(v)
            else:
                assert m.parse_entity_tag(v) == want, repr(v)
            count += 1
    assert count == sum(len(alphabet) ** n for n in range(0, 5))


def test_parse_lists_against_oracle():
    alphabet = ['"a"', 'W/"b"', '*', ',', ' ', '\t', '"', 'x', 'W/', ',,']
    count = 0
    for n in range(1, 5):
        for tup in itertools.product(alphabet, repeat=n):
            v = ''.join(tup)
            try:
                want = _olist(v)
            except OErr:
                with pytest.raises(ValueError):
                    m.parse_precondition_list(v, 'if-match')
            else:
                assert m.parse_precondition_list(v, 'if-match') == want, repr(v)
            count += 1
    assert count == sum(len(alphabet) ** n for n in range(1, 5))


def test_parse_check_order_and_caps():
    refuse('parse_entity_tag', 'bad_type:value', (None,))
    refuse('parse_entity_tag', 'bad_value:value.size', ('"' + 'x' * 8191 + '"',))
    refuse('parse_precondition_list', 'bad_type:value', (None, 5))
    refuse('parse_precondition_list', 'bad_value:value.size', ('"' + 'x' * 8191 + '"', 5))
    refuse('parse_precondition_list', 'bad_type:field', ('*', None))
    refuse('parse_precondition_list', 'bad_value:field', ('*', 'bad'))
    tracemalloc.start()
    try:
        for v in ('"' + 'x' * 8191 + '"', 'x' * 8193):
            with pytest.raises(ValueError):
                m.parse_entity_tag(v)
        cur, peak = tracemalloc.get_traced_memory()
        assert peak < 3 * 10 ** 6
    finally:
        tracemalloc.stop()


def test_format_exact_and_round_trip():
    assert m.format_entity_tag(('etag', False, 'xyzzy')) == '"xyzzy"'
    assert m.format_entity_tag(('etag', True, 'xyzzy')) == 'W/"xyzzy"'
    assert m.format_entity_tag(('etag', False, '')) == '""'
    assert m.format_precondition_list(('star',), 'if-match') == '*'
    assert m.format_precondition_list(('tags', (('etag', True, '1'), ('etag', False, '2'))), 'if-none-match') == 'W/"1", "2"'
    for fn, args in SUCCESSES:
        if fn == 'parse_entity_tag':
            t = m.parse_entity_tag(*args)
            assert m.parse_entity_tag(m.format_entity_tag(t)) == t
        elif fn == 'parse_precondition_list':
            t = m.parse_precondition_list(*args)
            assert m.parse_precondition_list(m.format_precondition_list(t, args[1]), args[1]) == t


def test_format_mismatch_guard(monkeypatch):
    orig = m.parse_entity_tag
    monkeypatch.setattr(m, 'parse_entity_tag', lambda v: ('etag', True, 'other'))
    with pytest.raises(ValueError) as e:
        m.format_entity_tag(('etag', False, 'a'))
    assert str(e.value).endswith(':format_entity_tag:bad_value:tree.mismatch')
    monkeypatch.setattr(m, 'parse_entity_tag', orig)


def test_exact_type_guards_subclass_and_falsy_inputs():
    refuse('parse_entity_tag', 'bad_type:value', (SS('"a"'),))
    refuse('parse_entity_tag', 'bad_type:value', (SB(b'"a"'),))
    refuse('format_entity_tag', 'bad_type:tree', (ST(('etag', False, 'a')),))
    refuse('format_entity_tag', 'bad_value:tree.shape', (('etag', IS(0), 'a'),))
    assert m.parse_precondition_list('*', 'if-match') == ('star',)
    assert m.strong_compare(('etag', False, ''), ('etag', False, '')) is True
    assert m.strong_compare(('etag', True, ''), ('etag', True, '')) is False
    assert m.weak_compare(('etag', True, ''), ('etag', False, '')) is True


def test_module_constants_exact():
    assert m.TAG == 'preconditions'
    assert m.FIELD_CAP == 8192
    assert m.FIELDS == ('if-match', 'if-none-match')


def test_format_list_mismatch_guard(monkeypatch):
    orig = m.parse_precondition_list
    monkeypatch.setattr(m, 'parse_precondition_list', lambda v, f: ('star',))
    with pytest.raises(ValueError) as e:
        m.format_precondition_list(('tags', (('etag', False, 'a'),)), 'if-match')
    assert str(e.value).endswith(':format_precondition_list:bad_value:tree.mismatch')
    monkeypatch.setattr(m, 'parse_precondition_list', orig)


def test_comparison_example_table_exact():
    p = m.parse_entity_tag
    rows = [(('W/"1"', 'W/"1"'), False, True), (('W/"1"', 'W/"2"'), False, False),
            (('W/"1"', '"1"'), False, True), (('"1"', '"1"'), True, True)]
    for (a, b), strong, weak in rows:
        ta, tb = p(a), p(b)
        assert m.strong_compare(ta, tb) is strong, (a, b)
        assert m.weak_compare(ta, tb) is weak, (a, b)
        assert m.strong_compare(tb, ta) is strong
        assert m.weak_compare(tb, ta) is weak


def test_comparison_strong_opaque_differ():
    p = m.parse_entity_tag
    a, b = p('"1"'), p('"2"')
    assert m.strong_compare(a, b) is False
    assert m.strong_compare(b, a) is False
    assert m.weak_compare(a, b) is False


def test_precedence_data_exact():
    assert m.PRECEDENCE == (
        (1, 'if-match', True, None, None, None, '412-unless-already-succeeded', 3),
        (2, 'if-unmodified-since', True, 'if-match', None, None, '412-unless-already-succeeded', 3),
        (3, 'if-none-match', False, None, None, None, '304-if-get-or-head-else-412', 5),
        (4, 'if-modified-since', False, 'if-none-match', ('GET', 'HEAD'), None, '304', 5),
        (5, 'if-range', False, None, ('GET',), ('range',), '206-if-validator-matches-and-range-applicable', 6),
        (6, None, False, None, None, None, 'perform-requested-action', 6))
    assert m.precedence() == m.PRECEDENCE
    assert m.constants() == {'field_cap': 8192, 'precedence_steps': 6}
    assert type(m.precedence()) is tuple
