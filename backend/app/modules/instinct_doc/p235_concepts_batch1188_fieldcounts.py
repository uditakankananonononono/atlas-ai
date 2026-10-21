"""b1188 RFC 5322 section 3.6 header field occurrence counts.

Source: RFC 5322 (Resnick, October 2008), section 3.6 (Field Definitions),
the min/max occurrence table and its Notes column. Only the NUMBER of times
each field occurs is checked, never the field bodies. The RFC says: "The only
required header fields are the origination date field and the originator
address field(s)." Five resent rows carry the note
"One per block - see 3.6.6"; the resent-date row adds that the field is
required when other resent fields are present, and the resent-sender row adds
that the field must occur with a multi-address resent-from. For a
multi-address originator field the rule is "Otherwise, both fields SHOULD
appear." The section 3.6.6 prose says Resent-From and Resent-Date MUST both
be sent when resent fields are used, which is stronger than the table, where
only resent-date carries the conditional requirement; this module implements
the table.
Thirty-one errata exist for RFC 5322 in the errata data used; four touch section
3.6 and are named here. 2816 (Rejected, Technical, section 3.6.2, reply-to
syntax): read, NOT applied. 2950 (Held for Document Update, Technical,
section 3.6, the fields ABNF): read, NOT applied; it rewrites the ABNF
repetition, not the count table. 3048 (Held for Document Update, Editorial,
section 3.6.6, wording): read, NOT applied. 3979 (Verified, Technical,
sections 3.6.7 and 4.5.7, the received-token syntax): read, NOT applied; it
changes the Received field body syntax, not any occurrence count, so no
Verified erratum changes the rules implemented here.
OURS design choices (not sourced from the RFC): the wire-name to table-kind
mapping including 'date' for orig-date and 'received' and 'return-path' for
trace; every unknown well-formed name is kind optional-field; the caps
NAME_MAX 64, FIELDS_MAX 4096 and COUNT_MAX 255; the violation codes and their
table-row order; a resent block is a maximal contiguous run of resent fields;
non-resent and non-trace entries passed to check_block are ignored; trace,
comments, keywords and optional-field entries are ignored by the count checks
because the table sets no limit for them; the conditional MUST rules are pure
predicates (needs_sender, needs_resent_sender) because mailbox counts live in
field bodies, which are out of scope. SOURCED: the 22 table rows with their
min and max numbers, the one-per-block resent rule with resent-date required
when any resent field is present, and the multi-address sender rules.
Errors raise ValueError P235:<name>:<code>. Well-formed but over- or
under-counted input returns a tuple of violation codes, never an exception.
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

SCOPE = 'RFC 5322 section 3.6 header field occurrence counts'
NOT_CLAIMED = ('field body syntax or semantics', 'mailbox counts inside any field', 'ordering rules beyond maximal resent runs', 'obsolete field syntax', 'message transmission')
ADJACENT = ('RFC 5322 sections 3.6.1 to 3.6.7 field semantics', 'RFC 5321 trace field handling', 'RFC 2045 MIME header fields')
CLAIMS = False

NAME_MAX = 64
FIELDS_MAX = 4096
COUNT_MAX = 255

NAMES = {
    'date': 'orig-date',
    'from': 'from',
    'sender': 'sender',
    'reply-to': 'reply-to',
    'to': 'to',
    'cc': 'cc',
    'bcc': 'bcc',
    'message-id': 'message-id',
    'in-reply-to': 'in-reply-to',
    'references': 'references',
    'subject': 'subject',
    'comments': 'comments',
    'keywords': 'keywords',
    'resent-date': 'resent-date',
    'resent-from': 'resent-from',
    'resent-sender': 'resent-sender',
    'resent-to': 'resent-to',
    'resent-cc': 'resent-cc',
    'resent-bcc': 'resent-bcc',
    'resent-msg-id': 'resent-msg-id',
    'received': 'trace',
    'return-path': 'trace',
}
RESENT = ('resent-date', 'resent-from', 'resent-sender', 'resent-to', 'resent-cc', 'resent-bcc', 'resent-msg-id')
MAIN = ('orig-date', 'from', 'sender', 'reply-to', 'to', 'cc', 'bcc', 'message-id', 'in-reply-to', 'references', 'subject')
REQUIRED = ('orig-date', 'from')


def _canon(name):
    return NAMES.get(name.lower(), 'optional-field')


def _name(f, name):
    if type(name) is not str:
        f('name-type')
    if len(name) > NAME_MAX:
        f('name-length')
    if name == '':
        f('name-invalid')
    for c in name:
        if ord(c) < 33 or ord(c) == 58 or ord(c) > 126:
            f('name-invalid')
    return _canon(name)


def kind(name):
    f = make_fail('kind')
    return _name(f, name)


def _count(f, mailboxes):
    if type(mailboxes) is not int:
        f('count-type')
    if mailboxes < 0 or mailboxes > COUNT_MAX:
        f('count-range')
    return mailboxes > 1


def needs_sender(mailboxes):
    f = make_fail('needs_sender')
    return _count(f, mailboxes)


def needs_resent_sender(mailboxes):
    f = make_fail('needs_resent_sender')
    return _count(f, mailboxes)


def _struct(f, fields):
    if type(fields) is not tuple and type(fields) is not list:
        f('fields-type')
    if len(fields) > FIELDS_MAX:
        f('fields-length')
    kinds = []
    for name in fields:
        kinds.append(_name(f, name))
    return kinds


def _main(kinds):
    out = []
    for row in MAIN:
        n = 0
        for k in kinds:
            if k == row:
                n += 1
        if row in REQUIRED and n == 0:
            out.append(row + '-missing')
        if n > 1:
            out.append(row + '-many')
    return tuple(out)


def _block(kinds):
    out = []
    n = 0
    for row in RESENT:
        c = 0
        for k in kinds:
            if k == row:
                c += 1
        n += c
        if c > 1:
            out.append(row + '-many')
        if row == 'resent-date':
            d = c
    if n > 0 and d == 0:
        out.insert(0, 'resent-date-missing')
    return tuple(out)


def check_counts(fields):
    f = make_fail('check_counts')
    kinds = _struct(f, fields)
    return _main(kinds)


def check_block(fields):
    f = make_fail('check_block')
    kinds = _struct(f, fields)
    return _block(kinds)


def check_message(fields):
    f = make_fail('check_message')
    kinds = _struct(f, fields)
    out = list(_main(kinds))
    run = []
    for k in kinds:
        if k in RESENT:
            run.append(k)
        else:
            out.extend(_block(run))
            run = []
    out.extend(_block(run))
    return tuple(out)
