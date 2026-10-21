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

MOD = 'app.modules.instinct_doc.p235_concepts_batch1211_cache_control'
REG = 'app.modules.instinct_doc.p235_concepts_registry'
m = importlib.import_module(MOD)


@pytest.fixture(autouse=True)
def _hang_guard():
    def boom(signum, frame):
        raise AssertionError('test exceeded 30 seconds')
    old = signal.signal(signal.SIGALRM, boom)
    signal.setitimer(signal.ITIMER_REAL, 30.0)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


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

_MODULE_DOCSTRING = 'P235 batch 1211: RFC 9111 (HTTP Caching) Section 5.2 (the Cache-Control header field\nand its request and response directives), Section 5.2.3 (extension directives) and\nSection 1.2.2 (delta-seconds), as a parser of a Cache-Control field value for a given\nrole and a formatter back.\n\nSTATUS OF THE RFC: RFC 9111 (June 2022, Standards Track) obsoletes RFC 7234. RFC 7234\nand every other RFC are not relied on.\nOVERLAP (OURS SCOPE): the unit is the grammar of the field value for the two roles; the\nAge (5.1), Expires (5.3) and Vary header fields and the freshness, age and validation\nrules belong to other units or to none and are not modelled.\n\nQUOTED FROM THE RAW RFC TEXT, read 2026-10-21 from the official plain text file\nhttps://www.rfc-editor.org/rfc/rfc9111.txt as 84477 bytes, sha256\naeb52adb3279d5f23dae34f68af11bd5cef0a0aff7ffcd014c9ca93c5302cf3e, 0 page breaks (form feeds), 0 page footer lines ("[Page"), and a\nbyte order mark at its start (not in any passage). Each of the 20 passages below is one\ncontiguous run of whole lines of that raw file, copied without elision or change; the raw\nline numbers are in each passage title. The rest of the RFC is not quoted and not modelled.\n\nPASSAGE 1 (RFC 9111 Section 5.2, the field and the directive grammar, raw lines 1083-1109)\n\n   The "Cache-Control" header field is used to list directives for\n   caches along the request/response chain.  Cache directives are\n   unidirectional, in that the presence of a directive in a request does\n   not imply that the same directive is present or copied in the\n   response.\n\n   See Section 5.2.3 for information about how Cache-Control directives\n   defined elsewhere are handled.\n\n   A proxy, whether or not it implements a cache, MUST pass cache\n   directives through in forwarded messages, regardless of their\n   significance to that application, since the directives might apply to\n   all recipients along the request/response chain.  It is not possible\n   to target a directive to a specific cache.\n\n   Cache directives are identified by a token, to be compared case-\n   insensitively, and have an optional argument that can use both token\n   and quoted-string syntax.  For the directives defined below that\n   define arguments, recipients ought to accept both forms, even if a\n   specific form is required for generation.\n\n     Cache-Control   = #cache-directive\n\n     cache-directive = token [ "=" ( token / quoted-string ) ]\n\n   For the cache directives defined below, no argument is defined (nor\n   allowed) unless stated otherwise.\n\nPASSAGE 2 (RFC 9111 Section 5.2.1.1, max-age (request), raw lines 1116-1129)\n\n5.2.1.1.  max-age\n\n   Argument syntax:\n\n      delta-seconds (see Section 1.2.2)\n\n   The max-age request directive indicates that the client prefers a\n   response whose age is less than or equal to the specified number of\n   seconds.  Unless the max-stale request directive is also present, the\n   client does not wish to receive a stale response.\n\n   This directive uses the token form of the argument syntax: e.g.,\n   \'max-age=5\' not \'max-age="5"\'.  A sender MUST NOT generate the\n   quoted-string form.\n\nPASSAGE 3 (RFC 9111 Section 5.2.1.2, max-stale, raw lines 1131-1146)\n\n5.2.1.2.  max-stale\n\n   Argument syntax:\n\n      delta-seconds (see Section 1.2.2)\n\n   The max-stale request directive indicates that the client will accept\n   a response that has exceeded its freshness lifetime.  If a value is\n   present, then the client is willing to accept a response that has\n   exceeded its freshness lifetime by no more than the specified number\n   of seconds.  If no value is assigned to max-stale, then the client\n   will accept a stale response of any age.\n\n   This directive uses the token form of the argument syntax: e.g.,\n   \'max-stale=10\' not \'max-stale="10"\'.  A sender MUST NOT generate the\n   quoted-string form.\n\nPASSAGE 4 (RFC 9111 Section 5.2.1.3, min-fresh, raw lines 1148-1162)\n\n5.2.1.3.  min-fresh\n\n   Argument syntax:\n\n      delta-seconds (see Section 1.2.2)\n\n   The min-fresh request directive indicates that the client prefers a\n   response whose freshness lifetime is no less than its current age\n   plus the specified time in seconds.  That is, the client wants a\n   response that will still be fresh for at least the specified number\n   of seconds.\n\n   This directive uses the token form of the argument syntax: e.g.,\n   \'min-fresh=20\' not \'min-fresh="20"\'.  A sender MUST NOT generate the\n   quoted-string form.\n\nPASSAGE 5 (RFC 9111 Section 5.2.1.4, no-cache (request), raw lines 1164-1168)\n\n5.2.1.4.  no-cache\n\n   The no-cache request directive indicates that the client prefers a\n   stored response not be used to satisfy the request without successful\n   validation on the origin server.\n\nPASSAGE 6 (RFC 9111 Section 5.2.1.5, no-store (request), raw lines 1170-1187)\n\n5.2.1.5.  no-store\n\n   The no-store request directive indicates that a cache MUST NOT store\n   any part of either this request or any response to it.  This\n   directive applies to both private and shared caches.  "MUST NOT\n   store" in this context means that the cache MUST NOT intentionally\n   store the information in non-volatile storage and MUST make a best-\n   effort attempt to remove the information from volatile storage as\n   promptly as possible after forwarding it.\n\n   This directive is not a reliable or sufficient mechanism for ensuring\n   privacy.  In particular, malicious or compromised caches might not\n   recognize or obey this directive, and communications networks might\n   be vulnerable to eavesdropping.\n\n   Note that if a request containing this directive is satisfied from a\n   cache, the no-store request directive does not apply to the already\n   stored response.\n\nPASSAGE 7 (RFC 9111 Section 5.2.1.6, no-transform (request), raw lines 1189-1193)\n\n5.2.1.6.  no-transform\n\n   The no-transform request directive indicates that the client is\n   asking for intermediaries to avoid transforming the content, as\n   defined in Section 7.7 of [HTTP].\n\nPASSAGE 8 (RFC 9111 Section 5.2.1.7, only-if-cached, raw lines 1195-1201)\n\n5.2.1.7.  only-if-cached\n\n   The only-if-cached request directive indicates that the client only\n   wishes to obtain a stored response.  Caches that honor this request\n   directive SHOULD, upon receiving it, respond with either a stored\n   response consistent with the other constraints of the request or a\n   504 (Gateway Timeout) status code.\n\nPASSAGE 9 (RFC 9111 Section 5.2.2 intro and Section 5.2.2.1, max-age (response), raw lines 1203-1220)\n\n5.2.2.  Response Directives\n\n   This section defines cache response directives.  A cache MUST obey\n   the Cache-Control directives defined in this section.\n\n5.2.2.1.  max-age\n\n   Argument syntax:\n\n      delta-seconds (see Section 1.2.2)\n\n   The max-age response directive indicates that the response is to be\n   considered stale after its age is greater than the specified number\n   of seconds.\n\n   This directive uses the token form of the argument syntax: e.g.,\n   \'max-age=5\' not \'max-age="5"\'.  A sender MUST NOT generate the\n   quoted-string form.\n\nPASSAGE 10 (RFC 9111 Section 5.2.2.2, must-revalidate, raw lines 1222-1244)\n\n5.2.2.2.  must-revalidate\n\n   The must-revalidate response directive indicates that once the\n   response has become stale, a cache MUST NOT reuse that response to\n   satisfy another request until it has been successfully validated by\n   the origin, as defined by Section 4.3.\n\n   The must-revalidate directive is necessary to support reliable\n   operation for certain protocol features.  In all circumstances, a\n   cache MUST NOT ignore the must-revalidate directive; in particular,\n   if a cache is disconnected, the cache MUST generate an error response\n   rather than reuse the stale response.  The generated status code\n   SHOULD be 504 (Gateway Timeout) unless another error status code is\n   more applicable.\n\n   The must-revalidate directive ought to be used by servers if and only\n   if failure to validate a request could cause incorrect operation,\n   such as a silently unexecuted financial transaction.\n\n   The must-revalidate directive also permits a shared cache to reuse a\n   response to a request containing an Authorization header field\n   (Section 11.6.2 of [HTTP]), subject to the above requirement on\n   revalidation (Section 3.5).\n\nPASSAGE 11 (RFC 9111 Section 5.2.2.3, must-understand, raw lines 1246-1256)\n\n5.2.2.3.  must-understand\n\n   The must-understand response directive limits caching of the response\n   to a cache that understands and conforms to the requirements for that\n   response\'s status code.\n\n   A response that contains the must-understand directive SHOULD also\n   contain the no-store directive.  When a cache that implements the\n   must-understand directive receives a response that includes it, the\n   cache SHOULD ignore the no-store directive if it understands and\n   implements the status code\'s caching requirements.\n\nPASSAGE 12 (RFC 9111 Section 5.2.2.4, no-cache (response), raw lines 1258-1293)\n\n5.2.2.4.  no-cache\n\n   Argument syntax:\n\n      #field-name\n\n   The no-cache response directive, in its unqualified form (without an\n   argument), indicates that the response MUST NOT be used to satisfy\n   any other request without forwarding it for validation and receiving\n   a successful response; see Section 4.3.\n\n   This allows an origin server to prevent a cache from using the\n   response to satisfy a request without contacting it, even by caches\n   that have been configured to send stale responses.\n\n   The qualified form of the no-cache response directive, with an\n   argument that lists one or more field names, indicates that a cache\n   MAY use the response to satisfy a subsequent request, subject to any\n   other restrictions on caching, if the listed header fields are\n   excluded from the subsequent response or the subsequent response has\n   been successfully revalidated with the origin server (updating or\n   removing those fields).  This allows an origin server to prevent the\n   reuse of certain header fields in a response, while still allowing\n   caching of the rest of the response.\n\n   The field names given are not limited to the set of header fields\n   defined by this specification.  Field names are case-insensitive.\n\n   This directive uses the quoted-string form of the argument syntax.  A\n   sender SHOULD NOT generate the token form (even if quoting appears\n   not to be needed for single-entry lists).\n\n      |  *Note:* The qualified form of the directive is often handled by\n      |  caches as if an unqualified no-cache directive was received;\n      |  that is, the special handling for the qualified form is not\n      |  widely implemented.\n\nPASSAGE 13 (RFC 9111 Section 5.2.2.5, no-store (response), raw lines 1295-1313)\n\n5.2.2.5.  no-store\n\n   The no-store response directive indicates that a cache MUST NOT store\n   any part of either the immediate request or the response and MUST NOT\n   use the response to satisfy any other request.\n\n   This directive applies to both private and shared caches.  "MUST NOT\n   store" in this context means that the cache MUST NOT intentionally\n   store the information in non-volatile storage and MUST make a best-\n   effort attempt to remove the information from volatile storage as\n   promptly as possible after forwarding it.\n\n   This directive is not a reliable or sufficient mechanism for ensuring\n   privacy.  In particular, malicious or compromised caches might not\n   recognize or obey this directive, and communications networks might\n   be vulnerable to eavesdropping.\n\n   Note that the must-understand cache directive overrides no-store in\n   certain circumstances; see Section 5.2.2.3.\n\nPASSAGE 14 (RFC 9111 Section 5.2.2.6, no-transform (response), raw lines 1315-1319)\n\n5.2.2.6.  no-transform\n\n   The no-transform response directive indicates that an intermediary\n   (regardless of whether it implements a cache) MUST NOT transform the\n   content, as defined in Section 7.7 of [HTTP].\n\nPASSAGE 15 (RFC 9111 Section 5.2.2.7, private, raw lines 1321-1353)\n\n5.2.2.7.  private\n\n   Argument syntax:\n\n      #field-name\n\n   The unqualified private response directive indicates that a shared\n   cache MUST NOT store the response (i.e., the response is intended for\n   a single user).  It also indicates that a private cache MAY store the\n   response, subject to the constraints defined in Section 3, even if\n   the response would not otherwise be heuristically cacheable by a\n   private cache.\n\n   If a qualified private response directive is present, with an\n   argument that lists one or more field names, then only the listed\n   header fields are limited to a single user: a shared cache MUST NOT\n   store the listed header fields if they are present in the original\n   response but MAY store the remainder of the response message without\n   those header fields, subject the constraints defined in Section 3.\n\n   The field names given are not limited to the set of header fields\n   defined by this specification.  Field names are case-insensitive.\n\n   This directive uses the quoted-string form of the argument syntax.  A\n   sender SHOULD NOT generate the token form (even if quoting appears\n   not to be needed for single-entry lists).\n\n      |  *Note:* This usage of the word "private" only controls where\n      |  the response can be stored; it cannot ensure the privacy of the\n      |  message content.  Also, the qualified form of the directive is\n      |  often handled by caches as if an unqualified private directive\n      |  was received; that is, the special handling for the qualified\n      |  form is not widely implemented.\n\nPASSAGE 16 (RFC 9111 Section 5.2.2.8, proxy-revalidate, raw lines 1355-1367)\n\n5.2.2.8.  proxy-revalidate\n\n   The proxy-revalidate response directive indicates that once the\n   response has become stale, a shared cache MUST NOT reuse that\n   response to satisfy another request until it has been successfully\n   validated by the origin, as defined by Section 4.3.  This is\n   analogous to must-revalidate (Section 5.2.2.2), except that proxy-\n   revalidate does not apply to private caches.\n\n   Note that proxy-revalidate on its own does not imply that a response\n   is cacheable.  For example, it might be combined with the public\n   directive (Section 5.2.2.9), allowing the response to be cached while\n   requiring only a shared cache to revalidate when stale.\n\nPASSAGE 17 (RFC 9111 Section 5.2.2.9, public, raw lines 1369-1382)\n\n5.2.2.9.  public\n\n   The public response directive indicates that a cache MAY store the\n   response even if it would otherwise be prohibited, subject to the\n   constraints defined in Section 3.  In other words, public explicitly\n   marks the response as cacheable.  For example, public permits a\n   shared cache to reuse a response to a request containing an\n   Authorization header field (Section 3.5).\n\n   Note that it is unnecessary to add the public directive to a response\n   that is already cacheable according to Section 3.\n\n   If a response with the public directive has no explicit freshness\n   information, it is heuristically cacheable (Section 4.2.2).\n\nPASSAGE 18 (RFC 9111 Section 5.2.2.10, s-maxage, raw lines 1384-1406)\n\n5.2.2.10.  s-maxage\n\n   Argument syntax:\n\n      delta-seconds (see Section 1.2.2)\n\n   The s-maxage response directive indicates that, for a shared cache,\n   the maximum age specified by this directive overrides the maximum age\n   specified by either the max-age directive or the Expires header\n   field.\n\n   The s-maxage directive incorporates the semantics of the\n   proxy-revalidate response directive (Section 5.2.2.8) for a shared\n   cache.  A shared cache MUST NOT reuse a stale response with s-maxage\n   to satisfy another request until it has been successfully validated\n   by the origin, as defined by Section 4.3.  This directive also\n   permits a shared cache to reuse a response to a request containing an\n   Authorization header field, subject to the above requirements on\n   maximum age and revalidation (Section 3.5).\n\n   This directive uses the token form of the argument syntax: e.g.,\n   \'s-maxage=10\' not \'s-maxage="10"\'.  A sender MUST NOT generate the\n   quoted-string form.\n\nPASSAGE 19 (RFC 9111 Section 5.2.3, extension directives, raw lines 1408-1416)\n\n5.2.3.  Extension Directives\n\n   The Cache-Control header field can be extended through the use of one\n   or more extension cache directives.  A cache MUST ignore unrecognized\n   cache directives.\n\n   Informational extensions (those that do not require a change in cache\n   behavior) can be added without changing the semantics of other\n   directives.\n\nPASSAGE 20 (RFC 9111 Section 1.2.2, delta-seconds, raw lines 214-234)\n\n   The delta-seconds rule specifies a non-negative integer, representing\n   time in seconds.\n\n     delta-seconds  = 1*DIGIT\n\n   A recipient parsing a delta-seconds value and converting it to binary\n   form ought to use an arithmetic type of at least 31 bits of non-\n   negative integer range.  If a cache receives a delta-seconds value\n   greater than the greatest integer it can represent, or if any of its\n   subsequent calculations overflows, the cache MUST consider the value\n   to be 2147483648 (2^31) or the greatest positive integer it can\n   conveniently represent.\n\n      |  *Note:* The value 2147483648 is here for historical reasons,\n      |  represents infinity (over 68 years), and does not need to be\n      |  stored in binary form; an implementation could produce it as a\n      |  string if any overflow occurs, even if the calculations are\n      |  performed with an arithmetic type incapable of directly\n      |  representing that number.  What matters here is that an\n      |  overflow be detected and not treated as a negative value in\n      |  later calculations.\n\nERRATA: the RFC Editor errata index (https://www.rfc-editor.org/errata.json, which now\nredirects to the RFC Editor API; read 2026-10-21 through the redirect as 11766165 bytes, sha256\n2771053324fcbbc3f775f4b6d7514c204ba1a4c65077c4fa866614d392640c66) holds\nthese records.\nRFC 9111, 4 records:\n- ID 7695 (Rejected, Technical, Section 4.3.2)\n- ID 9004 (Reported, Technical, Section 3.5)\n- ID 9166 (Held for Document Update, Technical, Section 5.2.3)\n- ID 9185 (Reported, Technical, Section 4.3.4)\nRFC 7234, 5 records (obsoleted by RFC 9111, not relied on):\n- ID 4479 (Rejected, Editorial, Section 5.3)\n- ID 4616 (Rejected, Editorial, GLOBAL)\n- ID 4674 (Verified, Editorial, Section 5.4)\n- ID 5564 (Rejected, Technical, Section 4.2.4)\n- ID 6279 (Held for Document Update, Technical, Section 4.2.4)\nRFC 9111 ID 9166 (Held for Document Update, Technical, Section 5.2.3) is on the quoted\nextension paragraph: the correction adds a sentence saying other HTTP extensions (such as\nheader fields) can also modify the operation of a cache. It does not change the rule this\nunit relies on (a cache MUST ignore unrecognized cache directives), so the parser keeps\nextension directives as the printed text states (RELIANCE PINNED). ID 7695 (Rejected,\nTechnical, Section 4.3.2), ID 9004 (Reported, Technical, Section 3.5) and ID 9185\n(Reported, Technical, Section 4.3.4) are filed on sections outside this unit\'s scope and\nare ledgered only. RFC 7234 records are on an obsoleted text and are ledgered only.\n\nSIDE OF THE LINE: this unit takes one Cache-Control field value as text and a role\n("request" or "response") and returns a tagged tuple, or takes the tuple and writes the\nfield value back. What a cache does with a directive (store, reuse, validate, the\nqualified handling of no-cache and private, the 2^31 overflow convention of 1.2.2) is not\ndecided here; a delta value is returned exactly as written.\n\nSOURCED FROM THE PASSAGES ABOVE: the field value is a #-list of cache-directive, each\n"token [ "=" ( token / quoted-string ) ]"; directive names are compared\ncase-insensitively; an argument can use both token and quoted-string syntax and recipients\nought to accept both forms even when a specific form is required for generation; for the\ndirectives defined there no argument is defined (nor allowed) unless stated otherwise; a\nproxy passes cache directives through and a cache MUST ignore unrecognized cache\ndirectives; the request directives are max-age, max-stale, min-fresh, no-cache, no-store,\nno-transform and only-if-cached; the response directives are max-age, must-revalidate,\nmust-understand, no-cache, no-store, no-transform, private, proxy-revalidate, public and\ns-maxage; max-age (both roles), min-fresh and s-maxage take delta-seconds and use the\ntoken form for generation (a sender MUST NOT generate the quoted-string form); max-stale\ntakes an optional delta-seconds (no value means a stale response of any age) and uses the\ntoken form for generation; no-cache and private in a response take an optional #field-name\nargument and use the quoted-string form (a sender SHOULD NOT generate the token form);\ndelta-seconds is 1*DIGIT.\n\nDECISIONS OURS, where the RFC allows a choice or is silent (each pinned by a test):\n- A tree is ("cache_control", role, directives) with role "request" or "response" and\n  directives a tuple of (name, argument) in order. The name is lowercase. The argument is\n  None; ("delta", n) with n the exact integer; ("names", (field_name, ...)) with the field\n  names lowercase for the qualified no-cache and private; ("token", text) or ("quoted",\n  text) for an extension directive, recording the form the argument arrived in.\n- A directive known only in the other role is parsed as an extension directive and kept,\n  because a proxy passes directives through and a cache ignores what it does not recognize\n  (5.2.3); its argument keeps its form. Duplicate directives are kept in order: the RFC\n  does not state a rule for them.\n- A defined argument accepts both forms on parse (5.2): a delta-seconds reads the content\n  of either form (digits only), and a field-name list reads a quoted string of\n  comma-separated names or one token (the single-entry token form). The formatter always\n  writes the required form: token for delta-seconds (leading zeros are dropped, since\n  1*DIGIT allows them on receipt) and a quoted string for a field-name list.\n- A refusal is a ValueError whose code is "bad_type:<where>" or "bad_value:<where>".\n  parse_cache_control checks, in order: the type of value; its size (at most 8192 octets);\n  the type of role; the role itself; the characters of value (printable ASCII and HTAB\n  only); then each directive in order: the name (a non-empty token), the argument form\n  (a token or a quoted-string; its characters are already bounded by the field-value\n  check above, so only its terminators and a trailing escape are read here), then the\n  rule of the directive: an\n  argument where none is defined is bad_value:directive.argument; a missing, empty or\n  non-digit delta-seconds, or one above 10*2^31 (OURS cap: 1.2.2 caps the useful value\n  at 2^31 and this unit bounds the integer it builds), is bad_value:directive.delta; a\n  bad field-name list is bad_value:directive.names; a bad quoted-string is\n  bad_value:directive.quoted; an empty element (including a leading comma) is\n  bad_value:directive.name, and a bad separator after a directive (a trailing comma or\n  other non-comma text) is bad_value:value.list. The grammar allows no whitespace around "=" (token [ "=" ...\n  ]), so "max-age =5" reads as a bare max-age (its delta-seconds is missing) and\n  "no-store =5" as a directive followed by a bad separator; OWS around the commas of\n  the #-list is allowed.\n- format_cache_control checks the tree with exact types (an int is not a bool; order:\n  the type of the tree, its shape, the tag, the role, the directives tuple, then each\n  directive: pair shape, name, argument), builds the field value with one space after\n  each comma, refuses a result above 8192 octets (bad_value:tree.size), and re-parses\n  its own text: a refusal from that parse is passed on (with the name of the function\n  that was called), and a tree that does not come back equal is bad_value:tree.mismatch\n  (this catches an argument on a directive that allows none, a "token" argument that is\n  not a token, and the like).\n- constants() returns {"field_cap": 8192, "delta_max": 2147483648}.\n\nNOT MODELLED: see NOT_CLAIMED in the module: Age, Expires, Vary, freshness, validation\nand every other section of RFC 9111.\n'
_SCOPE = 'PARTIAL: RFC 9111 (HTTP Caching) Section 5.2: the Cache-Control directive grammar (5.2), the request directives of 5.2.1, the response directives of 5.2.2, the extension rule of 5.2.3, and delta-seconds from 1.2.2, as a parser and a formatter of the field value for a given role; no Age, no Expires, no Vary, no freshness or age calculation, no cache behavior'
_NOT_CLAIMED = ('Age (5.1), Expires (5.3), Pragma (5.4) and Warning (5.5), and every other field of RFC 9111', 'freshness, age and their calculations (4.2), including the 2^31 overflow convention of 1.2.2: a delta value is returned exactly as written', 'what a cache does with a directive: validation, storing, staleness, the qualified no-cache and private handling, and the Notes on deployment', 'the RFC 9110 #rule recipient tolerance for empty list elements: this unit refuses an empty element', 'RFC 9110 token, quoted-string, #list and field-value rules beyond what the quoted passages state, and every other RFC')
_ADJACENT = ('a directive known only in the other role is parsed as an extension directive and kept, because a proxy passes directives through and a cache ignores what it does not recognize (5.2.3)', 'duplicate directives are kept in order: the RFC does not state a rule for them', 'recipients accept both the token and the quoted-string form of a defined argument (5.2); the formatter generates the required form (token for delta-seconds, quoted for field-name lists)', 'leading zeros in delta-seconds are accepted (1*DIGIT) and the formatter writes the minimal decimal form')
EXPECT_DOC_SHA = 'c7725c9d357dfdbb6df1c2b0b6a620d75bef7800f96ca0e52d793a5fcd5083e5'
EXPECT_LEDGER = 'RFC 9111, 4 records:\n- ID 7695 (Rejected, Technical, Section 4.3.2)\n- ID 9004 (Reported, Technical, Section 3.5)\n- ID 9166 (Held for Document Update, Technical, Section 5.2.3)\n- ID 9185 (Reported, Technical, Section 4.3.4)\nRFC 7234, 5 records (obsoleted by RFC 9111, not relied on):\n- ID 4479 (Rejected, Editorial, Section 5.3)\n- ID 4616 (Rejected, Editorial, GLOBAL)\n- ID 4674 (Verified, Editorial, Section 5.4)\n- ID 5564 (Rejected, Technical, Section 4.2.4)\n- ID 6279 (Held for Document Update, Technical, Section 4.2.4)\n'
EXPECT_NREFUSALS = 166
EXPECT_NSUCCESSES = 52
import signal,sys
def _boom(n,f):
    sys.stderr.write('P235 b1211 TIMEOUT\n');signal.alarm(1);sys.exit(3)
signal.signal(signal.SIGALRM,_boom)
signal.alarm(30)
PC = 'parse_cache_control'
FF = 'format_cache_control'
REFUSALS = []
SUCCESSES = []
D = 'bad_value:'
T_ = 'bad_type:'
R = 'request'
S = 'response'

# value type and size, then role type and value (check order: value type, value size, role type, role, chars)
for a in ((None, R), (b'max-age=5', R), (SB(b'max-age=5'), R), (bytearray(b'max-age=5'), R), (5, R), ((), R), ([], R), (SS('max-age=5'), R)):
    REFUSALS.append((PC, a, T_ + 'value'))
REFUSALS.append((PC, ('x' * 8193, R), D + 'value.size'))
REFUSALS.append((PC, ('x,' * 4096 + ',', R), D + 'value.size'))
for a in (('max-age=5', None), ('max-age=5', 0), ('max-age=5', SB(b'request')), ('max-age=5', SS('request')), ('max-age=5', ()), ('max-age=5', b'request')):
    REFUSALS.append((PC, a, T_ + 'role'))
for a in (('max-age=5', ''), ('max-age=5', 'REQUEST'), ('max-age=5', 'Response'), ('max-age=5', 'req'), ('max-age=5', ' request'), ('\x7f', 'x')):
    REFUSALS.append((PC, a, D + 'role'))
for v in ('max-age=5\n', 'max-age=5\r', '\x0b', '\x00', '\x1f', '\x7f', '\xc3\xa9', 'max-age=5\x80', 'x="caf\xc3\xa9"', 'no-store\x7f'):
    REFUSALS.append((PC, (v, R), D + 'value.char'))
REFUSALS.append((PC, ('a\x01', 'bad'), D + 'role'))

# list and name
for v, c in (('', 'directive.name'), ('   ', 'directive.name'), ('\t', 'directive.name'), (',max-age=5', 'directive.name'),
             ('a,,b', 'directive.name'), ('a, ,b', 'directive.name'), ('=5', 'directive.name'), (' =5', 'directive.name'),
             ('max-age=5,', 'value.list'), ('max-age=5 , ', 'directive.name'), ('max-age=5;', 'value.list'), ('max-age=5 x', 'value.list'),
             ('no-store =5', 'value.list'), ('x="a"y', 'value.list'), ('max-age=5=6', 'value.list'),
             ('a@', 'value.list'), ('max-age=5,no-store;', 'value.list')):
    REFUSALS.append((PC, (v, R), D + c))
REFUSALS.append((PC, ('a@', S), D + 'value.list'))

# argument rules
for v, role in (('no-store=5', R), ('no-store=5', S), ('no-store=""', R), ('no-cache=x', R), ('no-transform=1', R), ('no-transform=1', S),
                ('only-if-cached=x', R), ('must-revalidate="x"', S), ('must-understand=x', S), ('public=x', S), ('proxy-revalidate=x', S),
                ('no-cache=""', R)):
    REFUSALS.append((PC, (v, role), D + 'directive.argument'))
for v, role in (('max-age=', R), ('x=', R), ('x= ', R), ('max-stale=', R)):
    REFUSALS.append((PC, (v, role), D + 'directive.argument'))

# delta
for v, role in (('max-age', R), ('max-age', S), ('max-age=x', R), ('max-age=5x', R), ('max-age="5x"', R), ('max-age=-5', R), ('max-age=+5', R),
                ('max-age=5.0', R), ('max-age=""', R), ('max-age=21474836481', R), ('max-age=99999999999', R), ('max-age =5', R),
                ('min-fresh', R), ('min-fresh=x', R), ('max-stale=12x', R), ('max-stale="x"', R),
                ('s-maxage', S), ('s-maxage=x', S), ('s-maxage="10x"', S)):
    REFUSALS.append((PC, (v, role), D + 'directive.delta'))

# quoted-string form
for v, role in (('x="a', R), ('x="a\\', R), ('max-age="5', R), ('no-cache="a', S)):
    REFUSALS.append((PC, (v, role), D + 'directive.quoted'))

# field-name lists
for v in ('no-cache=""', 'no-cache="x y"', 'no-cache="x,"', 'no-cache=",x"', 'no-cache="x,,y"', 'no-cache="x;y"', 'no-cache="x y, z"',
          'private=""', 'private="a@b"', 'private="a,b,"', 'private="a , , b"'):
    REFUSALS.append((PC, (v, S), D + 'directive.names'))

# successes (parse)
SUCCESSES += [
    (PC, ('max-age=5', R)), (PC, ('MAX-AGE=5', R)), (PC, ('Max-Age="5"', R)), (PC, ('max-age=007', R)), (PC, ('max-age=0', R)),
    (PC, ('max-age=2147483648', R)), (PC, ('max-age=21474836480', R)), (PC, ('max-stale', R)), (PC, ('max-stale=10', R)), (PC, ('max-stale="10"', R)),
    (PC, ('min-fresh=3', R)), (PC, ('no-cache, no-store, no-transform, only-if-cached', R)),
    (PC, (' max-age=5 ,no-store\t,\tpublic', R)), (PC, ('x' * 8188 + '=1', R)), (PC, ('x,' * 4095 + 'x', R)), (PC, ('x' * 8192, R)), (PC, ('x~=1', R)), (PC, ('x="~"', R)),
    (PC, ('public, must-revalidate, must-understand, proxy-revalidate, s-maxage=10', S)),
    (PC, ('no-cache="set-cookie"', S)), (PC, ('no-cache', S)), (PC, ('private', S)), (PC, ('private="a, b"', S)), (PC, ('private=token', S)),
    (PC, ('private="Set-Cookie, X-ID"', S)), (PC, ('community="UCI", x-flag, y-tok=v', R)), (PC, ('community="UCI", x-flag, y-tok=v', S)),
    (PC, ('private=5', R)), (PC, ('only-if-cached', S)), (PC, ('max-stale', S)), (PC, ('immutable', S)), (PC, ('stale-while-revalidate=30', S)),
    (PC, ('x=""', R)), (PC, ('x="a\\z"', R)), (PC, ('x="a\\"b"', R)), (PC, ('max-age=5, max-age=6', R)), (PC, ('no-cache, no-cache', S)),
    (PC, ('max-age=5', S)), (PC, ('s-maxage="10"', S)), (PC, ('no-cache="a"', S)),
]

# format refusals
TT = 'cache_control'
for a in (None, 'x', SB(b'x'), [], 5, {}):
    REFUSALS.append((FF, (a,), T_ + 'tree'))
REFUSALS.append((FF, (ST((TT, R, ())),), T_ + 'tree'))
for a in ((), (TT,), (TT, R), (TT, R, (), 'x'), (TT, R, (), (), ())):
    REFUSALS.append((FF, (a,), D + 'tree.shape'))
REFUSALS.append((FF, ((5, R, ()),), T_ + 'tree.tag'))
REFUSALS.append((FF, ((SS(TT), R, ()),), T_ + 'tree.tag'))
for t in (('frame', R, ()), ('', R, ()), ('CACHE_CONTROL', R, ())):
    REFUSALS.append((FF, (t,), D + 'tree.tag'))
for a in ((TT, 5, ()), (TT, SS(R), ()), (TT, None, ())):
    REFUSALS.append((FF, (a,), T_ + 'tree.role'))
for a in ((TT, 'x', ()), (TT, '', ())):
    REFUSALS.append((FF, (a,), D + 'tree.role'))
for a in ((TT, R, []), (TT, R, 'x'), (TT, R, None)):
    REFUSALS.append((FF, (a,), T_ + 'tree.directives'))
for a in ((TT, R, ('x',)), (TT, R, ([('a', None)],)), (TT, R, (ST(('a', None)),))):
    REFUSALS.append((FF, (a,), T_ + 'tree.directive'))
for a in ((TT, R, (('a',),)), (TT, R, (('a', None, None),))):
    REFUSALS.append((FF, (a,), D + 'tree.directive'))
REFUSALS.append((FF, ((TT, R, ((5, None),)),), T_ + 'tree.name'))
REFUSALS.append((FF, ((TT, R, ((SS('a'), None),)),), T_ + 'tree.name'))
for nm in ('', 'a b', 'a@', '\xe9'):
    REFUSALS.append((FF, ((TT, R, ((nm, None),)),), D + 'tree.name'))
for arg in ('x', 5, ST(('token', 'v'))):
    REFUSALS.append((FF, ((TT, R, (('a', arg),)),), T_ + 'tree.argument'))
for arg in (('x', 1), ('token',), ('token', 'v', 'w'), ('token', 5), ('token', 'a b'), ('quoted', 5)):
    REFUSALS.append((FF, ((TT, R, (('a', arg),)),), D + 'tree.argument'))
for arg in (('delta', '5'), ('delta', True), ('delta', IS(5)), ('delta', -1), ('delta', 21474836481)):
    REFUSALS.append((FF, ((TT, R, (('max-age', arg),)),), D + 'tree.delta'))
for arg in (('names', []), ('names', ['x']), ('names', 'x'), ('names', ()), ('names', (5,)), ('names', ('a b',)), ('names', (SS('a'),)), ('names', ('a', 5))):
    REFUSALS.append((FF, ((TT, S, (('no-cache', arg),)),), D + 'tree.names'))
REFUSALS.append((FF, ((TT, R, (('x' * 4000, None), ('y' * 5000, None))),), D + 'tree.size'))
REFUSALS.append((FF, ((TT, R, (('x', ('token', 'v' * 8191)),)),), D + 'tree.size'))
# re-parse pass-through and mismatch
REFUSALS.append((FF, ((TT, R, (('no-store', ('delta', 5)),)),), D + 'directive.argument'))
REFUSALS.append((FF, ((TT, R, (('max-age', None),)),), D + 'directive.delta'))
REFUSALS.append((FF, ((TT, R, (('MAX-AGE', ('delta', 5)),)),), D + 'tree.mismatch'))
REFUSALS.append((FF, ((TT, R, (('x', ('names', ('a',))),)),), D + 'tree.mismatch'))
REFUSALS.append((FF, ((TT, S, (('private', ('names', ('A',))),)),), D + 'tree.mismatch'))

# format successes
_SUCC_TREES = [
    (TT, R, ()),
    (TT, S, ()),
    (TT, R, (('max-age', ('delta', 5)),)),
    (TT, R, (('max-age', ('delta', 0)), ('max-stale', None), ('no-store', None))),
    (TT, S, (('no-cache', ('names', ('set-cookie', 'x-id'))),)),
    (TT, S, (('private', ('names', ('a',))), ('public', None), ('s-maxage', ('delta', 10)))),
    (TT, S, (('community', ('quoted', 'UCI')), ('x-flag', None), ('y-tok', ('token', 'v')))),
    (TT, S, (('x', ('quoted', 'a b"c\\d')),)),
    (TT, R, (('x', ('quoted', '')),)),
    (TT, R, (('max-age', ('delta', 21474836480)),)),
    (TT, R, (('x' * 4070, None), ('y' * 4096, None))),
    (TT, R, (('x' * 8192, None),)),
]
for _t in _SUCC_TREES:
    SUCCESSES.append((FF, (_t,)))
del _t, _SUCC_TREES


_PUBLIC = {'find_spec', 'make_fail', 'FIELD_CAP', 'TAG', 'ROLES', 'TCHARS', 'DIGITS', 'VCHARS', 'DELTA_MAX', 'ARGS',
           'FULL', 'constants', '_tok', '_ows', '_quoted', '_delta', '_names', '_argument', 'parse_cache_control',
           '_quote', '_arg_text', '_build', 'format_cache_control', 'SCOPE', 'NOT_CLAIMED', 'ADJACENT'}
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


OTOKEN = set("!#$%&'*+-.^_`|~0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz")
ODELTA_REQ = {'request': {'max-age', 'min-fresh'}, 'response': {'max-age', 's-maxage'}}
ODELTA_OPT = {'request': {'max-stale'}, 'response': set()}
ONAMES = {'request': set(), 'response': {'no-cache', 'private'}}


def _osegs(value):
    segs = []
    cur = []
    q = False
    for c in value:
        if q:
            cur.append(c)
            if c == '"':
                q = False
        elif c == '"':
            q = True
            cur.append(c)
        elif c == ',':
            segs.append(''.join(cur))
            cur = []
        else:
            cur.append(c)
    if q:
        raise OErr('unterminated')
    segs.append(''.join(cur))
    return segs


def _oquoted(arg):
    if len(arg) < 2 or arg[0] != '"' or arg[-1] != '"':
        raise OErr('form')
    out = []
    i = 1
    while i < len(arg) - 1:
        c = arg[i]
        if c == '\\':
            i += 1
            if i >= len(arg) - 1:
                raise OErr('escape')
            c = arg[i]
            if not (c == '\t' or c == ' ' or 0x21 <= ord(c) <= 0x7e):
                raise OErr('escape')
            out.append(c)
        elif c == '"':
            raise OErr('inner quote')
        elif c in ('\t', ' ') or 0x21 <= ord(c) <= 0x7e:
            out.append(c)
        else:
            raise OErr('qdtext')
        i += 1
    return ''.join(out)


def oparse(value, role):
    for c in value:
        if c != '\t' and not (32 <= ord(c) <= 126):
            raise OErr('char')
    out = []
    for seg in _osegs(value):
        seg = seg.strip(' \t')
        if not seg:
            raise OErr('empty')
        if '=' in seg:
            name, arg = seg.split('=', 1)
            if not name or any(c not in OTOKEN for c in name):
                raise OErr('name')
            if arg.startswith('"') or '"' in arg:
                text = _oquoted(arg)
                form = 'quoted'
            else:
                if not arg or any(c not in OTOKEN for c in arg):
                    raise OErr('arg')
                text = arg
                form = 'token'
        else:
            name, text, form = seg, None, None
            if not name or any(c not in OTOKEN for c in name):
                raise OErr('name')
        name = name.lower()
        if name in ODELTA_REQ[role] or name in ODELTA_OPT[role]:
            if text is None:
                if name in ODELTA_REQ[role]:
                    raise OErr('delta missing')
                out.append((name, None))
                continue
            if not text.isdigit():
                raise OErr('delta')
            v = 0
            for c in text:
                v = v * 10 + ord(c) - 48
            if v > 21474836480:
                raise OErr('delta cap')
            out.append((name, ('delta', v)))
        elif name in ONAMES[role]:
            if text is None:
                out.append((name, None))
            else:
                names = []
                for piece in text.split(','):
                    piece = piece.strip(' \t')
                    if not piece or any(c not in OTOKEN for c in piece):
                        raise OErr('names')
                    names.append(piece.lower())
                out.append((name, ('names', tuple(names))))
        elif name in ONONE[role]:
            if text is not None:
                raise OErr('no argument allowed')
            out.append((name, None))
        else:
            out.append((name, None if text is None else (form, text)))
    return ('cache_control', role, tuple(out))


ONONE = {'request': {'no-cache', 'no-store', 'no-transform', 'only-if-cached'},
         'response': {'must-revalidate', 'must-understand', 'no-store', 'no-transform', 'proxy-revalidate', 'public'}}

EXACTS = [
    ('max-age=5', 'request', ('cache_control', 'request', (('max-age', ('delta', 5)),))),
    ('MAX-AGE=5', 'request', ('cache_control', 'request', (('max-age', ('delta', 5)),))),
    ('max-age="5"', 'request', ('cache_control', 'request', (('max-age', ('delta', 5)),))),
    ('max-age=007', 'request', ('cache_control', 'request', (('max-age', ('delta', 7)),))),
    ('max-stale', 'request', ('cache_control', 'request', (('max-stale', None),))),
    ('max-stale=0', 'request', ('cache_control', 'request', (('max-stale', ('delta', 0)),))),
    ('no-cache, no-store, no-transform, only-if-cached', 'request',
     ('cache_control', 'request', (('no-cache', None), ('no-store', None), ('no-transform', None), ('only-if-cached', None)))),
    ('no-cache="set-cookie"', 'response', ('cache_control', 'response', (('no-cache', ('names', ('set-cookie',))),))),
    ('private="Set-Cookie, X-ID"', 'response', ('cache_control', 'response', (('private', ('names', ('set-cookie', 'x-id'))),))),
    ('private=Token', 'response', ('cache_control', 'response', (('private', ('names', ('token',))),))),
    ('public, s-maxage=10', 'response', ('cache_control', 'response', (('public', None), ('s-maxage', ('delta', 10))))),
    ('community="UCI", x-flag, y-tok=v', 'response',
     ('cache_control', 'response', (('community', ('quoted', 'UCI')), ('x-flag', None), ('y-tok', ('token', 'v'))))),
    ('private=5', 'request', ('cache_control', 'request', (('private', ('token', '5')),))),
    ('only-if-cached', 'response', ('cache_control', 'response', (('only-if-cached', None),))),
    ('max-age=5, max-age=6', 'request', ('cache_control', 'request', (('max-age', ('delta', 5)), ('max-age', ('delta', 6))))),
    ('x="a\\zb"', 'request', ('cache_control', 'request', (('x', ('quoted', 'azb')),))),
    ('\tmax-age=5\t,\tno-store ', 'request', ('cache_control', 'request', (('max-age', ('delta', 5)), ('no-store', None)))),
    ('x=""', 'request', ('cache_control', 'request', (('x', ('quoted', '')),))),
    ('max-age=21474836480', 'request', ('cache_control', 'request', (('max-age', ('delta', 21474836480)),))),
    ('immutable', 'response', ('cache_control', 'response', (('immutable', None),))),
]


def test_module_docstring_and_literals_exact():
    assert hashlib.sha256(m.__doc__.encode('utf-8')).hexdigest() == EXPECT_DOC_SHA
    assert m.SCOPE == _SCOPE
    assert m.NOT_CLAIMED == _NOT_CLAIMED
    assert m.ADJACENT == _ADJACENT
    assert m.TAG == 'cache_control'
    assert m.FIELD_CAP == 8192
    assert m.DELTA_MAX == 2147483648
    assert m.ROLES == ('request', 'response')
    assert m.FULL is False
    assert m.ARGS == {
        'request': {'max-age': 'delta', 'max-stale': 'delta?', 'min-fresh': 'delta', 'no-cache': 'none', 'no-store': 'none',
                    'no-transform': 'none', 'only-if-cached': 'none'},
        'response': {'max-age': 'delta', 'must-revalidate': 'none', 'must-understand': 'none', 'no-cache': 'names?', 'no-store': 'none',
                     'no-transform': 'none', 'private': 'names?', 'proxy-revalidate': 'none', 'public': 'none', 's-maxage': 'delta'},
    }
    assert m.TCHARS == "!#$%&'*+-.^_`|~" + '0123456789' + 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' + 'abcdefghijklmnopqrstuvwxyz'
    assert m.DIGITS == '0123456789'
    assert m.VCHARS == ''.join(chr(c) for c in range(0x21, 0x7f))
    assert m.constants() == {'field_cap': 8192, 'delta_max': 2147483648}
    for fn in (m.parse_cache_control, m.format_cache_control, m.constants,
               m._tok, m._ows, m._quoted, m._delta, m._names, m._argument, m._quote, m._arg_text, m._build):
        assert fn.__doc__ is None
    src = pathlib.Path(m.__file__).read_bytes()
    assert all(b < 128 for b in src)
    codepart = src.decode().split('"' * 3 + chr(10), 1)[1]
    for junk in ('if False', 'or True', '[:0]', 'and True', 'or 1', 'and 1'):
        assert junk not in codepart
    assert m.constants() is not m.constants()
    assert type(m.NOT_CLAIMED) is tuple and len(m.NOT_CLAIMED) == 5 and all(x.isascii() for x in m.NOT_CLAIMED)
    assert type(m.ADJACENT) is tuple and len(m.ADJACENT) == 4 and all(x.isascii() for x in m.ADJACENT)
    tree = ast.parse(src.decode())
    imports = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
    assert [(type(n).__name__, n.module) for n in imports] == [('ImportFrom', 'importlib.util'), ('ImportFrom', REG)]
    called = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert 'int' not in called and 'float' not in called and 'eval' not in called and 'exec' not in called


def test_docstring_header_passages_and_sources():
    doc = m.__doc__
    head = doc.split('PASSAGE 1 (')[0]
    assert 'verbatim' not in head.lower()
    assert doc.count('\nPASSAGE ') == 20
    assert '84477' in head
    assert 'aeb52adb3279d5f23dae34f68af11bd5cef0a0aff7ffcd014c9ca93c5302cf3e' in head
    assert doc.count('\n- ID ') == 9
    parts = re.split(r'\nPASSAGE \d+ \(', doc)[1:]
    assert len(parts) == 20
    for p in parts:
        assert '\f' not in p
        assert '[Page' not in p
        assert '\r' not in p


def test_errata_ledger_exact():
    assert EXPECT_LEDGER in m.__doc__


def test_refusals_and_successes_tables_exact():
    assert len(REFUSALS) == EXPECT_NREFUSALS
    for fn, a, c in REFUSALS:
        refuse(fn, c, a)
    assert len(SUCCESSES) == EXPECT_NSUCCESSES
    for fn, a in SUCCESSES:
        getattr(m, fn)(*a)


def test_parse_exact_samples():
    for value, role, want in EXACTS:
        got = m.parse_cache_control(value, role)
        assert got == want, (value, role, got, want)
        assert type(got) is tuple and type(got[2]) is tuple
        assert oparse(value, role) == want


def test_parse_exhaustive_short_values_against_oracle():
    alpha = ('a', '=', '"', ',', ' ', '\t', '5', '\\', ';', '@')
    n = 0
    for w in itertools.product(alpha, repeat=3):
        v = ''.join(w)
        for role in ('request', 'response'):
            try:
                owant = oparse(v, role)
            except OErr:
                assert code_of('parse_cache_control', (v, role)) is not None, (v, role)
            else:
                assert m.parse_cache_control(v, role) == owant, (v, role)
            n += 1
    assert n == 2 * 1000


def test_parse_random_corpus_and_mutations_against_oracle():
    rng = random.Random(1211)
    seeds = ['max-age=5', 'no-cache="a, b"', 'private', 'x="q"', 'max-stale, only-if-cached', 's-maxage=10',
             'a,,b', 'x="a\\z"', 'max-age =5', 'no-store =5', ',', '""', 'x= ', 'max-age="5x"', 'no-cache="x,"']
    alphabet = 'abxyz5=,"\\ ;@\t-_\xe9'
    for _ in range(4000):
        v = rng.choice(seeds)
        for _ in range(rng.randrange(1, 4)):
            k = rng.randrange(3)
            if k == 0 and v:
                i = rng.randrange(len(v))
                v = v[:i] + rng.choice(alphabet) + v[i + 1:]
            elif k == 1:
                i = rng.randrange(len(v) + 1)
                v = v[:i] + rng.choice(alphabet) + v[i:]
            elif v:
                i = rng.randrange(len(v))
                v = v[:i] + v[i + 1:]
        role = rng.choice(('request', 'response'))
        try:
            owant = oparse(v, role)
        except OErr:
            assert code_of('parse_cache_control', (v, role)) is not None, (v, role)
        else:
            assert m.parse_cache_control(v, role) == owant, (v, role, owant)


def test_parse_check_order_and_caps():
    assert code_of('parse_cache_control', (None, 0)) == 'bad_type:value'
    assert code_of('parse_cache_control', ('x' * 8193, 0)) == 'bad_value:value.size'
    assert code_of('parse_cache_control', ('\x01', 0)) == 'bad_type:role'
    assert code_of('parse_cache_control', ('\x01', 'x')) == 'bad_value:role'
    assert code_of('parse_cache_control', ('\x01', 'request')) == 'bad_value:value.char'
    assert code_of('parse_cache_control', ('\x01no-store=5', 'request')) == 'bad_value:value.char'
    assert code_of('parse_cache_control', ('\x7f', 'request')) == 'bad_value:value.char'
    assert code_of('parse_cache_control', ('x\x7f', 'request')) == 'bad_value:value.char'
    assert code_of('parse_cache_control', ('max-age', 'request')) == 'bad_value:directive.delta'
    assert code_of('parse_cache_control', ('max-age=x', 'request')) == 'bad_value:directive.delta'
    assert code_of('parse_cache_control', ('max-age="5x"', 'request')) == 'bad_value:directive.delta'
    assert code_of('parse_cache_control', ('no-store=5', 'request')) == 'bad_value:directive.argument'
    assert code_of('parse_cache_control', ('no-cache=5', 'request')) == 'bad_value:directive.argument'
    assert code_of('parse_cache_control', ('no-cache="5"', 'request')) == 'bad_value:directive.argument'
    assert code_of('parse_cache_control', ('no-cache="a b"', 'response')) == 'bad_value:directive.names'
    assert code_of('parse_cache_control', ('x="a b"', 'request')) is None
    assert code_of('parse_cache_control', ('x="a', 'request')) == 'bad_value:directive.quoted'
    assert code_of('parse_cache_control', ('no-cache="a', 'response')) == 'bad_value:directive.quoted'
    assert code_of('parse_cache_control', ('max-age="5', 'request')) == 'bad_value:directive.quoted'
    assert code_of('parse_cache_control', ('max-age=', 'request')) == 'bad_value:directive.argument'
    assert code_of('parse_cache_control', ('x=', 'request')) == 'bad_value:directive.argument'
    assert code_of('parse_cache_control', ('max-age=5,', 'request')) == 'bad_value:value.list'
    assert code_of('parse_cache_control', (',', 'request')) == 'bad_value:directive.name'
    tracemalloc.start()
    try:
        m.parse_cache_control('x' * 8188 + '=1', 'request')
        cur, peak = tracemalloc.get_traced_memory()
        assert peak < 2000000, peak
    finally:
        tracemalloc.stop()


def test_format_exact_and_round_trip():
    cases = [
        (('cache_control', 'request', ()), ''),
        (('cache_control', 'request', (('max-age', ('delta', 5)),)), 'max-age=5'),
        (('cache_control', 'request', (('max-age', ('delta', 0)), ('max-stale', None), ('no-store', None))), 'max-age=0, max-stale, no-store'),
        (('cache_control', 'response', (('no-cache', ('names', ('set-cookie', 'x-id'))),)), 'no-cache="set-cookie, x-id"'),
        (('cache_control', 'response', (('private', ('names', ('a',))),)), 'private="a"'),
        (('cache_control', 'response', (('community', ('quoted', 'UCI')),)), 'community="UCI"'),
        (('cache_control', 'response', (('x', ('quoted', 'a b"c\\d')),)), 'x="a b\\"c\\\\d"'),
        (('cache_control', 'response', (('y', ('token', 'v')),)), 'y=v'),
        (('cache_control', 'response', (('x-flag', None),)), 'x-flag'),
        (('cache_control', 'request', (('max-age', ('delta', 21474836480)),)), 'max-age=21474836480'),
    ]
    for tree, want in cases:
        got = m.format_cache_control(tree)
        assert got == want, (tree, got, want)
        if tree[2] != ():
            assert m.parse_cache_control(got, tree[1]) == tree
    for value, role, tree in EXACTS:
        line = m.format_cache_control(tree)
        assert m.parse_cache_control(line, role) == tree
        assert m.format_cache_control(m.parse_cache_control(line, role)) == line
    rng = random.Random(9111)
    pool = ['max-age', 'max-stale', 'min-fresh', 'no-cache', 'no-store', 'no-transform', 'only-if-cached',
            'must-revalidate', 'must-understand', 'private', 'proxy-revalidate', 'public', 's-maxage', 'x-ext', 'y']
    for _ in range(3000):
        role = rng.choice(('request', 'response'))
        ds = []
        for _ in range(rng.randrange(0, 6)):
            nm = rng.choice(pool)
            known = m.ARGS[role].get(nm)
            if known is None:
                k = rng.randrange(3)
                ds.append((nm, None if k == 0 else ('token', 'tok') if k == 1 else ('quoted', 'a b')))
            elif known == 'none':
                ds.append((nm, None))
            elif known in ('delta', 'delta?'):
                ds.append((nm, None if known == 'delta?' and rng.randrange(2) else ('delta', rng.randrange(0, 10 ** 10))))
            else:
                ds.append((nm, None if rng.randrange(2) else ('names', ('a', 'b-c')[:rng.randrange(1, 3)])))
        tree = ('cache_control', role, tuple(ds))
        line = m.format_cache_control(tree)
        if tree[2] == ():
            assert line == ''
        else:
            assert m.parse_cache_control(line, role) == tree, (tree, line)


def test_format_check_order_and_caps():
    assert code_of('format_cache_control', (None,)) == 'bad_type:tree'
    assert code_of('format_cache_control', (('cache_control', 'request', ()),)) is None
    assert code_of('format_cache_control', (('cache_control', 'request'),)) == 'bad_value:tree.shape'
    assert code_of('format_cache_control', ((5, 'request', ()),)) == 'bad_type:tree.tag'
    assert code_of('format_cache_control', (('x', 5, ()),)) == 'bad_value:tree.tag'
    assert code_of('format_cache_control', (('cache_control', 5, 'x'),)) == 'bad_type:tree.role'
    assert code_of('format_cache_control', (('cache_control', 'x', 'x'),)) == 'bad_value:tree.role'
    assert code_of('format_cache_control', (('cache_control', 'request', 'x'),)) == 'bad_type:tree.directives'
    assert code_of('format_cache_control', (('cache_control', 'request', ('x',)),)) == 'bad_type:tree.directive'
    assert code_of('format_cache_control', (('cache_control', 'request', ((5,),)),)) == 'bad_value:tree.directive'
    assert code_of('format_cache_control', (('cache_control', 'request', ((5, None),)),)) == 'bad_type:tree.name'
    assert code_of('format_cache_control', (('cache_control', 'request', (('', 5),)),)) == 'bad_value:tree.name'
    assert code_of('format_cache_control', (('cache_control', 'request', (('x', 5),)),)) == 'bad_type:tree.argument'
    assert code_of('format_cache_control', (('cache_control', 'request', (('x', ('delta', 'a')),)),)) == 'bad_value:tree.delta'
    assert code_of('format_cache_control', (('cache_control', 'request', (('x', ('delta', 5)),)),)) == 'bad_value:tree.mismatch'
    tracemalloc.start()
    try:
        m.format_cache_control(('cache_control', 'request', (('x' * 4070, None), ('y' * 4096, None))))
        cur, peak = tracemalloc.get_traced_memory()
        assert peak < 2000000, peak
    finally:
        tracemalloc.stop()


def test_exact_type_guards_subclass_and_falsy_inputs():
    assert code_of('parse_cache_control', (SS('max-age=5'), 'request')) == 'bad_type:value'
    assert code_of('parse_cache_control', ('max-age=5', SS('request'))) == 'bad_type:role'
    assert code_of('format_cache_control', (ST(('cache_control', 'request', ())),)) == 'bad_type:tree'
    assert code_of('format_cache_control', ((SS('cache_control'), 'request', ()),)) == 'bad_type:tree.tag'
    assert code_of('format_cache_control', (('cache_control', SS('request'), ()),)) == 'bad_type:tree.role'
    assert code_of('format_cache_control', (('cache_control', 'request', ((SS('x'), None),)),)) == 'bad_type:tree.name'
    assert code_of('format_cache_control', (('cache_control', 'request', (('x', ST(('token', 'v'))),)),)) == 'bad_type:tree.argument'
    assert code_of('format_cache_control', (('cache_control', 'request', (('max-age', ('delta', IS(5))),)),)) == 'bad_value:tree.delta'
    assert code_of('format_cache_control', (('cache_control', 'request', (('max-age', ('delta', True)),)),)) == 'bad_value:tree.delta'
    assert code_of('parse_cache_control', ('max-age=0', 'request')) is None
    assert m.parse_cache_control('max-age=0', 'request')[2][0][1][1] == 0
    assert m.format_cache_control(('cache_control', 'request', (('max-age', ('delta', 0)),))) == 'max-age=0'
    assert m.format_cache_control(('cache_control', 'request', ())) == ''
    assert m.parse_cache_control('x=""', 'request')[2][0][1] == ('quoted', '')
