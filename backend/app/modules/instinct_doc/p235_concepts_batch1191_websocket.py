'''RFC 6455 "The WebSocket Protocol": the s5.2 base frame
format as a byte-level wire grammar (the FIN/RSV1-3/opcode
first octet, the MASK bit, the 7/16/64-bit payload-length
forms, the masking key and the payload), the s5.2 opcode
registry, the s5.5 control-frame constraints, and the
s5.5.1 close-frame body with the s7.4 status-code rules,
over one complete frame of Python bytes.  The opening
handshake (s4), message fragmentation sequencing (s5.4),
extension negotiation (s9), subprotocols and the security
considerations (s10) are out of scope.

Public API:

  websocket_frame_parse(data, expect_mask=None) -> a dict:
      'fin': the FIN bit as a bool,
      'opcode': the 4-bit opcode as an int,
      'opcode_name': one of "continuation", "text",
          "binary", "close", "ping", "pong",
      'is_control': True for the control opcodes 0x8-0xA,
      'masked': the MASK bit as a bool,
      'masking_key': the raw 4-byte masking key, or None
          when MASK is 0,
      'payload_length': the decoded payload length,
      'payload': the payload bytes, UNMASKED per s5.3,
      'header_length': the number of bytes before the
          payload (base header + extended length + masking
          key),
      'close_code': the close status code as an int, or
          None unless the frame is a Close carrying a body,
      'close_reason': the decoded UTF-8 reason string, or
          None unless the close body carries one.
  websocket_frame_is_valid(data, expect_mask=None) ->
      True iff websocket_frame_parse would succeed.

  expect_mask pins the sender's role: True requires the
  MASK bit set (s5.1: "a client MUST mask all frames that
  it sends to the server"); False requires it clear (s5.1:
  "A server MUST NOT mask any frames that it sends to the
  client"); None accepts either bit (role-neutral).

Grammar notes (verified against the RFC 6455 text): s5.2
defines the first octet as FIN, RSV1, RSV2, RSV3 and a
4-bit opcode, and the second as MASK plus a 7-bit payload
length.  RSV1-3 "MUST be 0 unless an extension is
negotiated that defines meanings for non-zero values";
extension negotiation is out of scope here, so any nonzero
RSV bit refuses.  The defined opcodes: "%x0 denotes a
continuation frame", "%x1 denotes a text frame", "%x2
denotes a binary frame", "%x3-7 are reserved for further
non-control frames", "%x8 denotes a connection close",
"%x9 denotes a ping", "%xA denotes a pong", "%xB-F are
reserved for further control frames"; "If an unknown
opcode is received, the receiving endpoint MUST _Fail the
WebSocket Connection_", so reserved opcodes refuse.  The
payload length rules: "if 0-125, that is the payload
length.  If 126, the following 2 bytes interpreted as a
16-bit unsigned integer are the payload length.  If 127,
the following 8 bytes interpreted as a 64-bit unsigned
integer (the most significant bit MUST be 0) are the
payload length.  Multibyte length quantities are expressed
in network byte order.  Note that in all cases, the
minimal number of bytes MUST be used to encode the length,
for example, the length of a 124-byte-long string can't
be encoded as the sequence 126, 0, 124."  s5.5: "Control
frames are identified by opcodes where the most
significant bit of the opcode is 1" and "All control
frames MUST have a payload length of 125 bytes or less
and MUST NOT be fragmented."  The s5.3 unmask transform:
"j = i MOD 4" and "transformed-octet-i = original-octet-i
XOR masking-key-octet-j"; "The masking does not affect
the length of the "Payload data"."  s5.5.1 close body:
"If there is a body, the first two bytes of the body MUST
be a 2-byte unsigned integer (in network byte order)
representing a status code with value /code/ defined in
Section 7.4.  Following the 2-byte integer, the body MAY
contain UTF-8-encoded data with value /reason/"; a
one-byte body cannot hold the mandatory 2-byte code, so it
refuses.  s7.4.1: 1005, 1006 and 1015 each "is a reserved
value and MUST NOT be set as a status code in a Close
control frame by an endpoint".  s7.4.2: "Status codes in
the range 0-999 are not used."  s8.1: "When an endpoint
is to interpret a byte stream as UTF-8 but finds that the
byte stream is not, in fact, a valid UTF-8 stream, that
endpoint MUST _Fail the WebSocket Connection_."

Profile decisions (OURS, not from the RFC text):
  - The expect_mask parameter and its role mapping; the
    default None is role-neutral.
  - Only the exact bytes type is accepted for the frame
    and only the exact bool type for expect_mask;
    subclasses refuse with the type code.
  - Continuation frames and fragmented DATA frames pass
    frame-level validation: the s5.4 sequencing rules (a
    continuation must follow an unfinished message, a new
    data frame must not start mid-message) are connection
    state, not frame grammar.
  - Text-frame payloads are NOT UTF-8-checked here: a
    fragmented text message can split a multi-byte
    sequence across frames (s5.4), and s8.1 binds when the
    endpoint interprets the reassembled stream.  A close
    reason cannot be fragmented (s5.5), so it IS checked.
  - Close status codes: only 0-999 ("not used", s7.4.2)
    and 1005/1006/1015 (explicit MUST NOT, s7.4.1)
    refuse.  1004 is accepted: s7.4.1 marks it "Reserved.
    The specific meaning might be defined in the future."
    with no MUST NOT, unlike the three refused values.
    Undefined codes in 1000-2999 and the 3000-3999 and
    4000-4999 ranges are accepted per the s7.4.2
    reservations; the text does not constrain 5000-65535.
  - Bytes beyond the declared payload length refuse: the
    function validates ONE complete frame, and the payload
    length "is the length of the "Extension data" + the
    length of the "Application data"", so trailing bytes
    belong to another frame.
  - Masking-key freshness and unpredictability (s5.3) are
    not frame-validatable: any 4 bytes pass as a key.
  - Size cap (OURS): _MAX_FRAME_LENGTH bytes for the whole
    wire frame.

Refusal order: bad_type:data.type before
bad_type:expect_mask.type before everything else; then the
frame length cap (bad_value:data.length),
bad_value:frame.short, bad_value:rsv.nonzero,
bad_value:opcode.reserved, the control rules
(bad_value:control.fragmented before
bad_value:control.length), bad_value:mask.mismatch, the
extended-length field (bad_value:frame.truncated.length16
or bad_value:frame.truncated.length64, then
bad_value:length.msb for the 64-bit form, then
bad_value:length.minimal),
bad_value:frame.truncated.masking_key,
bad_value:frame.truncated.payload before
bad_value:frame.trailing, then the close-body rules
(bad_value:close.body.short, bad_value:close.code.range
before bad_value:close.code.reserved,
bad_value:close.reason.utf8).

Errata (18 records: 3 Verified, 5 Rejected, 4 Held for
Document Update, 6 Reported; none folded).  The Verified
records touch the opening handshake, not the validated
frame grammar: Verified EID 3433 (s11.3.2, Technical)
concerns Sec-WebSocket-Extensions multiplicity in HTTP
responses; Verified EID 3473 (s4.1, Editorial) rewords the
client connection-wait rule; Verified EID 3150 (s4.1,
Technical) corrects the Sec-WebSocket-Key example value
"AQIDBAUGBwgJCgsMDQ4PEC==" to "AQIDBAUGBwgJCgsMDQ4PEA==".
Noted, not folded: Reported EID 7262 (s5.5.1, Technical)
would change the close reason from "MAY contain
UTF-8-encoded data" to data which "MUST be UTF-8-encoded";
this unit already enforces UTF-8 on the reason per s8.1,
so both readings validate identically here.  Reported EID
5288 (s5.2, Editorial) rewords the frame-masking-key ABNF;
Reported EID 4672 (s5.6, Technical), Reported EID 4919
(s7.4.1, Technical), Reported EID 6997 (s4.3/9.1,
Technical) and Reported EID 7608 (s7.1.1, Technical) do
not change the validated grammar.  Held for Document
Update EID 3227 (s7.4.1) rewords the 1011 description,
Held EID 3432 (s5.7) relabels an example, Held EID 4398
(s4.1) and Held EID 5498 (s11.2) touch handshake material;
none folded.  Rejected EID 3912 (s5.2) proposed renaming
frame-payload-length-63; the printed 63-bit grammar
stands.  Rejected EIDs 3215 (s5.3), 4184 (s5.4), 5453
(s4.1) and 8491 (s9.1) do not touch the validated grammar.
'''

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


_MAX_FRAME_LENGTH = 16777216

_OPCODES = {0x0: 'continuation', 0x1: 'text', 0x2: 'binary',
            0x8: 'close', 0x9: 'ping', 0xA: 'pong'}

_CLOSE_CODES_NEVER = frozenset((1005, 1006, 1015))


def _unmask(key, payload):
    out = bytearray(len(payload))
    for i in range(len(payload)):
        out[i] = payload[i] ^ key[i % 4]
    return bytes(out)


def websocket_frame_parse(data, expect_mask=None):
    'Validate one s5.2 WebSocket frame; return its fields.'
    f = make_fail('websocket_frame_parse')
    if type(data) is not bytes:
        f('bad_type:data.type')
    if expect_mask is not None and type(expect_mask) is not bool:
        f('bad_type:expect_mask.type')
    if len(data) > _MAX_FRAME_LENGTH:
        f('bad_value:data.length')
    if len(data) < 2:
        f('bad_value:frame.short')
    b0 = data[0]
    b1 = data[1]
    fin = bool(b0 & 0x80)
    if b0 & 0x70:
        f('bad_value:rsv.nonzero')
    opcode = b0 & 0x0F
    opcode_name = _OPCODES.get(opcode)
    if opcode_name is None:
        f('bad_value:opcode.reserved')
    if opcode >= 0x8:
        if not fin:
            f('bad_value:control.fragmented')
        if (b1 & 0x7F) > 125:
            f('bad_value:control.length')
    masked = bool(b1 & 0x80)
    if expect_mask is not None and masked is not expect_mask:
        f('bad_value:mask.mismatch')
    pos = 2
    marker = b1 & 0x7F
    if marker <= 125:
        payload_length = marker
    elif marker == 126:
        if len(data) < pos + 2:
            f('bad_value:frame.truncated.length16')
        payload_length = int.from_bytes(data[pos:pos + 2], 'big')
        pos += 2
        if payload_length < 126:
            f('bad_value:length.minimal')
    else:
        if len(data) < pos + 8:
            f('bad_value:frame.truncated.length64')
        if data[pos] & 0x80:
            f('bad_value:length.msb')
        payload_length = int.from_bytes(data[pos:pos + 8], 'big')
        pos += 8
        if payload_length < 65536:
            f('bad_value:length.minimal')
    if masked:
        if len(data) < pos + 4:
            f('bad_value:frame.truncated.masking_key')
        masking_key = data[pos:pos + 4]
        pos += 4
    else:
        masking_key = None
    if len(data) - pos < payload_length:
        f('bad_value:frame.truncated.payload')
    if len(data) - pos > payload_length:
        f('bad_value:frame.trailing')
    payload = data[pos:]
    if masked:
        payload = _unmask(masking_key, payload)
    close_code = None
    close_reason = None
    if opcode == 0x8:
        if len(payload) == 1:
            f('bad_value:close.body.short')
        if len(payload) >= 2:
            close_code = int.from_bytes(payload[0:2], 'big')
            if close_code < 1000:
                f('bad_value:close.code.range')
            if close_code in _CLOSE_CODES_NEVER:
                f('bad_value:close.code.reserved')
            if len(payload) > 2:
                try:
                    close_reason = payload[2:].decode('utf-8')
                except UnicodeDecodeError:
                    f('bad_value:close.reason.utf8')
    return {'fin': fin,
            'opcode': opcode,
            'opcode_name': opcode_name,
            'is_control': opcode >= 0x8,
            'masked': masked,
            'masking_key': masking_key,
            'payload_length': payload_length,
            'payload': payload,
            'header_length': pos,
            'close_code': close_code,
            'close_reason': close_reason}


def websocket_frame_is_valid(data, expect_mask=None):
    'True iff websocket_frame_parse(data, expect_mask) would succeed.'
    try:
        websocket_frame_parse(data, expect_mask)
    except ValueError:
        return False
    return True
