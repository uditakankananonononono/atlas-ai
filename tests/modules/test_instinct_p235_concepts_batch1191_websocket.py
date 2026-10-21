import ast
import builtins
import os
import importlib.util as iu
import pathlib
import random
import signal
import sys
import tempfile
import types
import pytest

REG = 'app.modules.instinct_doc.p235_concepts_registry'


@pytest.fixture(scope='module', autouse=True)
def load_module():
    global m
    from app.modules.instinct_doc import (
        p235_concepts_batch1191_websocket as mod)
    m = mod


@pytest.fixture(autouse=True)
def alarm():
    # No test may run away: a hanging mutant must die by assertion, and
    # fast enough that an accumulating loop cannot exhaust memory first.
    def stop(*a):
        raise AssertionError('test exceeded 30 seconds')
    old = signal.signal(signal.SIGALRM, stop)
    signal.setitimer(signal.ITIMER_REAL, 30.0)
    yield
    signal.setitimer(signal.ITIMER_REAL, 0)
    signal.signal(signal.SIGALRM, old)


_PFX = None


def _pfx():
    global _PFX
    if _PFX is None:
        try:
            m.make_fail('x')('c')
        except ValueError as e:
            msg = str(e)
            assert msg.endswith('x:c')
            _PFX = msg[:-len('x:c')]
        else:
            raise AssertionError('make_fail did not raise')
    return _PFX


def refuse(fn_name, code, *args):
    with pytest.raises(ValueError) as caught:
        getattr(m, fn_name)(*args)
    assert str(caught.value) == _pfx() + fn_name + ':' + code, (
        code, caught.value)


class _BytesSub(bytes):
    pass


FP = 'websocket_frame_parse'

_HELLO_UNMASKED = bytes.fromhex('810548656c6c6f')
_HELLO_MASKED = bytes.fromhex('818537fa213d7f9f4d5158')
_MASK_KEY = bytes.fromhex('37fa213d')


def _mask(key, payload):
    return bytes(b ^ key[i % 4] for i, b in enumerate(payload))


_SUCC_CACHE = None
_REFU_CACHE = None


def _success_corpus():
    global _SUCC_CACHE
    if _SUCC_CACHE is None:
        s = [(FP, (_HELLO_UNMASKED,)),
             (FP, (_HELLO_MASKED,)),
             (FP, (bytes.fromhex('010348656c'),)),
             (FP, (bytes.fromhex('80026c6f'),)),
             (FP, (bytes.fromhex('890548656c6c6f'),)),
             (FP, (bytes.fromhex('8a8537fa213d7f9f4d5158'),)),
             (FP, (bytes.fromhex('827e0100') + bytes(range(256)),)),
             (FP, (bytes.fromhex('827f0000000000010000')
                   + b'\x00' * 65536,)),
             (FP, (b'\x80\x00',)),
             (FP, (b'\x81\x00',)),
             (FP, (b'\x81\x80\x00\x00\x00\x00',)),
             (FP, (b'\x88\x00',)),
             (FP, (bytes.fromhex('880203e8'),)),
             (FP, (bytes.fromhex('880603e8646f6e65'),)),
             (FP, (bytes.fromhex('8882') + b'\x01\x02\x03\x04'
                   + bytes([0x03 ^ 0x01, 0xe8 ^ 0x02]),)),
             (FP, (_HELLO_MASKED, True)),
             (FP, (_HELLO_UNMASKED, False)),
             (FP, (b'\x89\x7d' + b'p' * 125,)),
             (FP, (b'\x82\x7e\xff\xff' + b'b' * 65535,)),
             (FP, (b'\x82\x7f\x00\x00\x00\x00\x00\x01\x00\x00'
                   + b'b' * 65536,)),
             (FP, (b'\x8a\xfd' + b'\x11\x22\x33\x44'
                   + _mask(b'\x11\x22\x33\x44', b'q' * 125), True)),
             (FP, (b'\x82\x7e\x00\x7e' + b'z' * 126,))]
        _SUCC_CACHE = s
    return _SUCC_CACHE

def _refusal_corpus():
    global _REFU_CACHE
    if _REFU_CACHE is None:
        c = []
        for bad in (None, 0, 1, True, False, 5.5, 'x81',
                    bytearray(b'\x81\x00'), memoryview(b'\x81\x00'),
                    [129, 0], (129, 0), {'f': 1},
                    _BytesSub(b'\x81\x00')):
            c.append((FP, 'bad_type:data.type', (bad,)))
        for bad_mask in (0, 1, 0.0, 'true', b'\x01', [], _BytesSub(b'')):
            c.append((FP, 'bad_type:expect_mask.type',
                      (b'\x81\x00', bad_mask)))
        c.append((FP, 'bad_value:data.length',
                  (b'x' * 16777217,)))
        for bad in (b'', b'\x81'):
            c.append((FP, 'bad_value:frame.short', (bad,)))
        for bad in (b'\xc1\x00', b'\xa1\x00', b'\x91\x00',
                    b'\xf1\x00', b'\xd2\x05Hello'):
            c.append((FP, 'bad_value:rsv.nonzero', (bad,)))
        for op in (0x3, 0x4, 0x5, 0x6, 0x7,
                   0xB, 0xC, 0xD, 0xE, 0xF):
            c.append((FP, 'bad_value:opcode.reserved',
                      (bytes([0x80 | op, 0x00]),)))
        for bad in (b'\x08\x00', b'\x09\x00', b'\x0a\x00'):
            c.append((FP, 'bad_value:control.fragmented', (bad,)))
        for bad in (b'\x89\x7e', b'\x8a\x7f', b'\x88\xff'):
            c.append((FP, 'bad_value:control.length', (bad,)))
        c.append((FP, 'bad_value:mask.mismatch',
                  (_HELLO_UNMASKED, True)))
        c.append((FP, 'bad_value:mask.mismatch',
                  (_HELLO_MASKED, False)))
        for bad in (b'\x82\x7e', b'\x82\x7e\x01'):
            c.append((FP, 'bad_value:frame.truncated.length16', (bad,)))
        for n in range(8):
            c.append((FP, 'bad_value:frame.truncated.length64',
                      (b'\x82\x7f' + b'\x00' * n,)))
        c.append((FP, 'bad_value:length.msb',
                  (b'\x82\x7f\x80\x00\x00\x00\x00\x00\x00\x00'
                   + b'\x00' * 8,)))
        c.append((FP, 'bad_value:length.msb',
                  (b'\x82\x7f\xff\xff\xff\xff\xff\xff\xff\xff',)))
        for bad in (b'\x82\x7e\x00\x00', b'\x82\x7e\x00\x01',
                    b'\x82\x7e\x00\x7d',
                    b'\x82\x7f\x00\x00\x00\x00\x00\x00\x00\x00',
                    b'\x82\x7f\x00\x00\x00\x00\x00\x00\x00\x7e',
                    b'\x82\x7f\x00\x00\x00\x00\x00\x00\xff\xff'):
            c.append((FP, 'bad_value:length.minimal', (bad,)))
        for bad in (b'\x81\x80', b'\x81\x80\x01',
                    b'\x81\x80\x01\x02\x03'):
            c.append((FP, 'bad_value:frame.truncated.masking_key',
                      (bad,)))
        for bad in (b'\x81\x05Hel', b'\x81\x05',
                    b'\x81\x85' + _MASK_KEY + b'Hel',
                    b'\x82\x7e\x01\x00' + b'\x00' * 255):
            c.append((FP, 'bad_value:frame.truncated.payload', (bad,)))
        for bad in (b'\x81\x02abc', b'\x81\x00x',
                    b'\x81\x81' + _MASK_KEY + b'ab'):
            c.append((FP, 'bad_value:frame.trailing', (bad,)))
        c.append((FP, 'bad_value:close.body.short', (b'\x88\x01\x03',)))
        for bad in (b'\x88\x02\x00\x00', b'\x88\x02\x00\x01',
                    b'\x88\x02\x03\xe7'):
            c.append((FP, 'bad_value:close.code.range', (bad,)))
        for bad in (b'\x88\x02\x03\xed', b'\x88\x02\x03\xee',
                    b'\x88\x02\x03\xf7'):
            c.append((FP, 'bad_value:close.code.reserved', (bad,)))
        for bad in (b'\x88\x03\x03\xe8\xff',
                    b'\x88\x03\x03\xe8\xc3',
                    b'\x88\x04\x03\xe8\xc0\xaf',
                    b'\x88\x04\x03\xe8\xe2\x82'):
            c.append((FP, 'bad_value:close.reason.utf8', (bad,)))
        _REFU_CACHE = c
    return _REFU_CACHE


def _bounded_call(fn_name, args, bound=1.0):
    'Run a parse under a hard real-time bound; AssertionError on overrun.'
    fn = getattr(m, fn_name)
    if not hasattr(signal, 'setitimer') or not hasattr(signal, 'SIGALRM'):
        return fn(*args)
    def stop(*a):
        raise AssertionError(
            'parse exceeded 1.0s bound: a scan loop did not advance')
    old = signal.signal(signal.SIGALRM, stop)
    signal.setitimer(signal.ITIMER_REAL, bound)
    try:
        return fn(*args)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


def test_loops_advance_under_time_bound():
    for fn_name, args in _success_corpus():
        _bounded_call(fn_name, args)
    try:
        _bounded_call(FP, (b'\x82\x7e\xff\xff' + b'b' * 65534,))
    except ValueError:
        pass
    else:
        raise AssertionError('truncated input must refuse, not hang')


def test_module_docstring_is_pinned_whole():
    assert m.__doc__ == __DOC__

def test_rfc_s5_7_examples():
    # s5.7: a single-frame unmasked text message
    r = m.websocket_frame_parse(bytes.fromhex('810548656c6c6f'))
    assert r['fin'] is True and r['opcode'] == 0x1
    assert r['opcode_name'] == 'text' and r['is_control'] is False
    assert r['masked'] is False and r['masking_key'] is None
    assert r['payload_length'] == 5 and r['payload'] == b'Hello'
    assert r['header_length'] == 2
    assert r['close_code'] is None and r['close_reason'] is None
    # s5.7: a single-frame masked text message
    r = m.websocket_frame_parse(bytes.fromhex('818537fa213d7f9f4d5158'))
    assert r['masked'] is True and r['masking_key'] == _MASK_KEY
    assert r['payload'] == b'Hello' and r['header_length'] == 6
    # s5.7: a fragmented unmasked text message, frame by frame
    r = m.websocket_frame_parse(bytes.fromhex('010348656c'))
    assert r['fin'] is False and r['opcode_name'] == 'text'
    assert r['payload'] == b'Hel'
    r = m.websocket_frame_parse(bytes.fromhex('80026c6f'))
    assert r['fin'] is True and r['opcode_name'] == 'continuation'
    assert r['payload'] == b'lo'
    # s5.7: unmasked Ping and masked Pong carrying "Hello"
    r = m.websocket_frame_parse(bytes.fromhex('890548656c6c6f'))
    assert r['opcode_name'] == 'ping' and r['is_control'] is True
    assert r['payload'] == b'Hello'
    r = m.websocket_frame_parse(bytes.fromhex('8a8537fa213d7f9f4d5158'))
    assert r['opcode_name'] == 'pong' and r['payload'] == b'Hello'
    # s5.7: 256 bytes of binary in a 16-bit length frame
    body = bytes(range(256))
    r = m.websocket_frame_parse(bytes.fromhex('827e0100') + body)
    assert r['opcode_name'] == 'binary' and r['payload'] == body
    assert r['payload_length'] == 256 and r['header_length'] == 4
    # s5.7: 64KiB of binary in a 64-bit length frame
    body = b'\x5a' * 65536
    r = m.websocket_frame_parse(
        bytes.fromhex('827f0000000000010000') + body)
    assert r['payload_length'] == 65536 and r['payload'] == body
    assert r['header_length'] == 10


def test_masking_transform_round_trip():
    # s5.3: transformed-octet-i = original-octet-i XOR key[i MOD 4];
    # masking does not change the payload length
    key = b'\xde\xad\xbe\xef'
    raw = bytes(range(17))
    wire = b'\x82\x91' + key + _mask(key, raw)
    r = m.websocket_frame_parse(wire)
    assert r['payload'] == raw and r['payload_length'] == 17
    assert r['masking_key'] == key and r['header_length'] == 6
    # an all-zero key leaves the payload byte-identical on the wire
    wire = b'\x82\x91' + b'\x00\x00\x00\x00' + raw
    assert m.websocket_frame_parse(wire)['payload'] == raw


def test_opcode_registry():
    for op, name in ((0x0, 'continuation'), (0x1, 'text'),
                     (0x2, 'binary'), (0x8, 'close'),
                     (0x9, 'ping'), (0xA, 'pong')):
        r = m.websocket_frame_parse(bytes([0x80 | op, 0x00]))
        assert r['opcode'] == op and r['opcode_name'] == name
        assert r['is_control'] is (op >= 0x8)
    for op in (0x3, 0x4, 0x5, 0x6, 0x7, 0xB, 0xC, 0xD, 0xE, 0xF):
        refuse(FP, 'bad_value:opcode.reserved',
               bytes([0x80 | op, 0x00]))
        assert m.websocket_frame_is_valid(bytes([0x80 | op, 0x00])) is False


def test_rsv_bits_refuse():
    for bad in (b'\xc1\x00', b'\xa1\x00', b'\x91\x00',
                b'\xf1\x00'):
        refuse(FP, 'bad_value:rsv.nonzero', bad)
    # an RSV bit refuses even on an otherwise valid masked frame
    refuse(FP, 'bad_value:rsv.nonzero',
           b'\xc1\x85' + _MASK_KEY + _mask(_MASK_KEY, b'Hello'))


def test_control_frame_rules():
    # control frames must not be fragmented
    for bad in (b'\x08\x00', b'\x09\x00', b'\x0a\x00'):
        refuse(FP, 'bad_value:control.fragmented', bad)
    # control payloads cap at 125; an extended-length marker refuses
    m.websocket_frame_parse(b'\x89\x7d' + b'p' * 125)
    refuse(FP, 'bad_value:control.length', b'\x89\x7e')
    refuse(FP, 'bad_value:control.length', b'\x8a\x7f')
    # the cap applies to the 7-bit marker before any extended parsing
    refuse(FP, 'bad_value:control.length', b'\x88\xff')


def test_payload_length_forms():
    # the 7-bit form carries 0..125 directly
    for n in (0, 1, 124, 125):
        r = m.websocket_frame_parse(bytes([0x82, n]) + b'd' * n)
        assert r['payload_length'] == n and r['header_length'] == 2
    # 126 and 65535 through the 16-bit form, in network byte order
    r = m.websocket_frame_parse(b'\x82\x7e\x00\x7e' + b'd' * 126)
    assert r['payload_length'] == 126 and r['header_length'] == 4
    r = m.websocket_frame_parse(b'\x82\x7e\xff\xff' + b'd' * 65535)
    assert r['payload_length'] == 65535
    # 65536 and up through the 64-bit form
    r = m.websocket_frame_parse(
        b'\x82\x7f\x00\x00\x00\x00\x00\x01\x00\x00'
        + b'd' * 65536)
    assert r['payload_length'] == 65536 and r['header_length'] == 10


def test_minimal_length_encoding():
    # the minimal number of bytes MUST be used (s5.2)
    refuse(FP, 'bad_value:length.minimal', b'\x82\x7e\x00\x00')
    refuse(FP, 'bad_value:length.minimal', b'\x82\x7e\x00\x7d')
    refuse(FP, 'bad_value:length.minimal',
           b'\x82\x7f\x00\x00\x00\x00\x00\x00\xff\xff')
    # exactly at the form boundaries the longer form is legal
    m.websocket_frame_parse(b'\x82\x7e\x00\x7e' + b'd' * 126)
    m.websocket_frame_parse(
        b'\x82\x7f\x00\x00\x00\x00\x00\x01\x00\x00'
        + b'd' * 65536)


def test_length64_msb_must_be_zero():
    refuse(FP, 'bad_value:length.msb',
           b'\x82\x7f\x80\x00\x00\x00\x00\x00\x00\x00'
           + b'\x00' * 8)
    # the largest legal 63-bit length still refuses on truncation,
    # proving the MSB check did not reject it
    refuse(FP, 'bad_value:frame.truncated.payload',
           b'\x82\x7f\x7f\xff\xff\xff\xff\xff\xff\xff')


def test_frame_truncations_and_trailing():
    refuse(FP, 'bad_value:frame.short', b'')
    refuse(FP, 'bad_value:frame.short', b'\x81')
    refuse(FP, 'bad_value:frame.truncated.length16', b'\x82\x7e\x01')
    for n in range(8):
        refuse(FP, 'bad_value:frame.truncated.length64',
               b'\x82\x7f' + b'\x00' * n)
    refuse(FP, 'bad_value:frame.truncated.masking_key',
           b'\x81\x80\x01\x02\x03')
    refuse(FP, 'bad_value:frame.truncated.payload', b'\x81\x05Hel')
    refuse(FP, 'bad_value:frame.truncated.payload',
           b'\x81\x85' + _MASK_KEY + b'Hel')
    refuse(FP, 'bad_value:frame.trailing', b'\x81\x02abc')
    refuse(FP, 'bad_value:frame.trailing', b'\x81\x00x')


def test_expect_mask_role_pin():
    # None is role-neutral; True requires masked; False unmasked
    m.websocket_frame_parse(_HELLO_MASKED)
    m.websocket_frame_parse(_HELLO_UNMASKED)
    m.websocket_frame_parse(_HELLO_MASKED, True)
    m.websocket_frame_parse(_HELLO_UNMASKED, False)
    refuse(FP, 'bad_value:mask.mismatch', _HELLO_UNMASKED, True)
    refuse(FP, 'bad_value:mask.mismatch', _HELLO_MASKED, False)
    # s5.1: a server MUST NOT mask; a client MUST mask
    r = m.websocket_frame_parse(
        b'\x88\x82' + b'\x01\x02\x03\x04'
        + bytes([0x03 ^ 0x01, 0xe8 ^ 0x02]), True)
    assert r['close_code'] == 1000 and r['masked'] is True

def test_close_frame_body():
    # no body: no code, no reason
    r = m.websocket_frame_parse(b'\x88\x00')
    assert r['close_code'] is None and r['close_reason'] is None
    # a one-byte body cannot hold the mandatory 2-byte code
    refuse(FP, 'bad_value:close.body.short', b'\x88\x01\x03')
    # code alone
    r = m.websocket_frame_parse(b'\x88\x02\x03\xe8')
    assert r['close_code'] == 1000 and r['close_reason'] is None
    # code + UTF-8 reason, network byte order code
    r = m.websocket_frame_parse(bytes.fromhex('880603e8646f6e65'))
    assert r['close_code'] == 1000 and r['close_reason'] == 'done'
    r = m.websocket_frame_parse(
        b'\x88\x08\x03\xe9' + 'gå'.encode('utf-8') + b' by')
    assert r['close_code'] == 1001 and r['close_reason'] == 'gå by'


def test_close_status_codes():
    # every s7.4.1 defined code passes
    for code in (1000, 1001, 1002, 1003, 1004, 1007, 1008, 1009,
                 1010, 1011):
        r = m.websocket_frame_parse(
            b'\x88\x02' + code.to_bytes(2, 'big'))
        assert r['close_code'] == code
    # reserved-for-others ranges and undefined 1000-2999 pass
    for code in (1012, 1016, 2999, 3000, 3999, 4000, 4999,
                 5000, 65535):
        r = m.websocket_frame_parse(
            b'\x88\x02' + code.to_bytes(2, 'big'))
        assert r['close_code'] == code
    # 0-999 are "not used" (s7.4.2)
    for code in (0, 1, 999):
        refuse(FP, 'bad_value:close.code.range',
               b'\x88\x02' + code.to_bytes(2, 'big'))
    # 1005, 1006, 1015 MUST NOT be set (s7.4.1)
    for code in (1005, 1006, 1015):
        refuse(FP, 'bad_value:close.code.reserved',
               b'\x88\x02' + code.to_bytes(2, 'big'))


def test_close_reason_must_be_utf8():
    # s5.5.1 + s8.1: invalid UTF-8 in the reason fails the frame
    refuse(FP, 'bad_value:close.reason.utf8',
           b'\x88\x03\x03\xe8\xff')
    refuse(FP, 'bad_value:close.reason.utf8',
           b'\x88\x03\x03\xe8\xc3')
    refuse(FP, 'bad_value:close.reason.utf8',
           b'\x88\x04\x03\xe8\xc0\xaf')
    # a lone surrogate encoding is not valid UTF-8 either
    refuse(FP, 'bad_value:close.reason.utf8',
           b'\x88\x05\x03\xe8\xed\xa0\x80')
    # the reason is checked on the UNMASKED body
    key = b'\x0a\x0b\x0c\x0d'
    body = b'\x03\xe8\xff'
    refuse(FP, 'bad_value:close.reason.utf8',
           b'\x88\x83' + key + _mask(key, body))


def test_close_body_rules_apply_after_unmasking():
    key = _MASK_KEY
    body = (1000).to_bytes(2, 'big') + 'okay ✓'.encode('utf-8')
    r = m.websocket_frame_parse(
        bytes([0x88, 0x80 | len(body)]) + key + _mask(key, body))
    assert r['close_code'] == 1000
    assert r['close_reason'] == 'okay ✓'
    assert r['payload'] == body


def test_result_shape_and_freshness():
    r = m.websocket_frame_parse(_HELLO_UNMASKED)
    assert list(r) == ['fin', 'opcode', 'opcode_name', 'is_control',
                       'masked', 'masking_key', 'payload_length',
                       'payload', 'header_length', 'close_code',
                       'close_reason']
    assert type(r['fin']) is bool and type(r['masked']) is bool
    assert type(r['is_control']) is bool
    assert type(r['opcode']) is int and type(r['opcode_name']) is str
    assert type(r['payload_length']) is int
    assert type(r['payload']) is bytes
    assert type(r['header_length']) is int
    a = m.websocket_frame_parse(_HELLO_MASKED)
    b = m.websocket_frame_parse(_HELLO_MASKED)
    assert a is not b and a == b
    a['payload'] = b'MUTATED'
    assert m.websocket_frame_parse(_HELLO_MASKED)['payload'] == b'Hello'


def test_header_length_by_form():
    assert m.websocket_frame_parse(b'\x81\x00')['header_length'] == 2
    assert m.websocket_frame_parse(
        b'\x81\x80' + _MASK_KEY)['header_length'] == 6
    assert m.websocket_frame_parse(
        b'\x82\x7e\x00\x7e' + b'd' * 126)['header_length'] == 4
    assert m.websocket_frame_parse(
        b'\x82\xfe\x00\x7e' + _MASK_KEY
        + _mask(_MASK_KEY, b'd' * 126))['header_length'] == 8
    assert m.websocket_frame_parse(
        b'\x82\x7f\x00\x00\x00\x00\x00\x01\x00\x00'
        + b'd' * 65536)['header_length'] == 10
    assert m.websocket_frame_parse(
        b'\x82\xff\x00\x00\x00\x00\x00\x01\x00\x00'
        + _MASK_KEY + _mask(_MASK_KEY, b'd' * 65536)
    )['header_length'] == 14

def test_frame_length_cap():
    # exactly at the OURS cap: accepted (127-form, unmasked)
    n = 16777216 - 10  # 10 header bytes: 2 base + 8 extended length
    wire = b'\x82\x7f' + n.to_bytes(8, 'big') + b'\x00' * n
    r = m.websocket_frame_parse(wire)
    assert r['payload_length'] == n
    # one byte over the cap refuses before any parsing
    refuse(FP, 'bad_value:data.length', b'x' * 16777217)


def test_exact_types_refuse():
    for bad in (None, 0, True, 5.5, 'x81', bytearray(b'\x81\x00'),
                memoryview(b'\x81\x00'), [129, 0], (129, 0),
                _BytesSub(b'\x81\x00')):
        refuse(FP, 'bad_type:data.type', bad)
        assert m.websocket_frame_is_valid(bad) is False
    for bad_mask in (0, 1, 'true', b'\x01'):
        refuse(FP, 'bad_type:expect_mask.type', b'\x81\x00', bad_mask)


def test_refusal_order():
    # type before length cap before short before rsv before opcode
    refuse(FP, 'bad_type:data.type', 0)
    refuse(FP, 'bad_value:data.length', b'x' * 16777217)
    refuse(FP, 'bad_value:frame.short', b'\x81')
    refuse(FP, 'bad_value:rsv.nonzero', b'\xc3\x00')
    refuse(FP, 'bad_value:opcode.reserved', b'\x83\x00')
    # control.fragmented before control.length
    refuse(FP, 'bad_value:control.fragmented', b'\x09\x7e')
    # control rules before mask.mismatch before the length field
    refuse(FP, 'bad_value:control.length', b'\x89\x7e', True)
    refuse(FP, 'bad_value:mask.mismatch', b'\x82\x7e', True)
    # truncation of the length field before msb before minimal
    refuse(FP, 'bad_value:frame.truncated.length64', b'\x82\x7f\x80')
    refuse(FP, 'bad_value:length.msb',
           b'\x82\x7f\x80\x00\x00\x00\x00\x00\x00\x00')
    refuse(FP, 'bad_value:length.minimal', b'\x82\x7e\x00\x00')
    # masking-key truncation before payload truncation before trailing
    refuse(FP, 'bad_value:frame.truncated.masking_key',
           b'\x81\x85\x01')
    refuse(FP, 'bad_value:frame.truncated.payload',
           b'\x81\x85' + _MASK_KEY + b'ab')
    refuse(FP, 'bad_value:frame.trailing', b'\x81\x01ab')
    # close rules: short before range before reserved before utf8
    refuse(FP, 'bad_value:close.body.short', b'\x88\x01\xff')
    refuse(FP, 'bad_value:close.code.range', b'\x88\x03\x00\x01\xff')
    refuse(FP, 'bad_value:close.code.reserved',
           b'\x88\x03\x03\xed\xff')
    refuse(FP, 'bad_value:close.reason.utf8', b'\x88\x03\x03\xe8\xff')


def test_is_valid_returns_exact_bool():
    v = m.websocket_frame_is_valid(_HELLO_UNMASKED)
    assert v is True and type(v) is bool
    assert m.websocket_frame_is_valid(_HELLO_MASKED, True) is True
    assert m.websocket_frame_is_valid(_HELLO_MASKED, False) is False
    assert m.websocket_frame_is_valid(b'\x83\x00') is False
    assert m.websocket_frame_is_valid(None) is False
    assert m.websocket_frame_is_valid('x81') is False


def test_constants_pinned_whole():
    assert m._MAX_FRAME_LENGTH == 16777216
    assert m._OPCODES == {0x0: 'continuation', 0x1: 'text',
                          0x2: 'binary', 0x8: 'close', 0x9: 'ping',
                          0xA: 'pong'}
    assert m._CLOSE_CODES_NEVER == frozenset((1005, 1006, 1015))


def test_function_docstrings_pinned_exact():
    assert m.websocket_frame_parse.__doc__ == (
        'Validate one s5.2 WebSocket frame; return its fields.')
    assert m.websocket_frame_is_valid.__doc__ == (
        'True iff websocket_frame_parse(data, expect_mask) would '
        'succeed.')


def test_module_namespace_is_pinned():
    names = set(vars(m))
    assert names == {
        '__name__', '__doc__', '__package__', '__loader__',
        '__spec__', '__file__', '__cached__', '__builtins__',
        'find_spec', 'make_fail',
        '_MAX_FRAME_LENGTH', '_OPCODES', '_CLOSE_CODES_NEVER',
        '_unmask',
        'websocket_frame_parse', 'websocket_frame_is_valid'}


def test_parse_is_deterministic_and_consistent():
    rng = random.Random(1191)
    for _ in range(400):
        blob = bytes(rng.randrange(256)
                     for _ in range(rng.randrange(0, 12)))
        try:
            r1 = m.websocket_frame_parse(blob)
        except ValueError:
            assert m.websocket_frame_is_valid(blob) is False
        else:
            assert m.websocket_frame_is_valid(blob) is True
            assert m.websocket_frame_parse(blob) == r1

def _f_lines():
    fname = pathlib.Path(m.__file__)
    tree = ast.parse(fname.read_text())
    lines = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == 'f'):
            lines.add(node.lineno)
    return lines, str(fname)


def test_corpus_drives_every_refusal_site_and_success_path():
    f_lines, fname = _f_lines()
    hits = set()

    def tracer(frame, event, arg):
        if event == 'line' and frame.f_code.co_filename == fname:
            hits.add(frame.f_lineno)
        return tracer

    sys.settrace(tracer)
    try:
        for fn_name, args in _success_corpus():
            getattr(m, fn_name)(*args)
        for fn_name, code, d in _refusal_corpus():
            raised = None
            try:
                getattr(m, fn_name)(*d)
            except ValueError as caught:
                raised = caught
            assert raised is not None, (fn_name, code)
    finally:
        sys.settrace(None)
    # no exemptions: every f() site in the module is corpus-reached
    assert f_lines <= hits, sorted(f_lines - hits)


# ---- no imports on any public call ----

def test_no_import_on_any_public_call():
    fname = str(pathlib.Path(m.__file__))
    f_lines, _ = _f_lines()
    hits = set()
    log = []

    def tracer(frame, event, arg):
        if event == 'line' and frame.f_code.co_filename == fname:
            hits.add(frame.f_lineno)
        return tracer

    real = builtins.__import__

    def hook(name, *a, **k):
        log.append(name)
        return real(name, *a, **k)

    sys.settrace(tracer)
    try:
        for fn_name, args in (
                _success_corpus()
                + [(fn, d) for fn, code, d in
                   _refusal_corpus()]):
            log = []
            builtins.__import__ = hook
            try:
                try:
                    getattr(m, fn_name)(*args)
                except ValueError:
                    pass
                # the is_valid twin is a public call too (its
                # True AND False paths): an inserted import in
                # either body dies here
                is_valid = getattr(
                    m, fn_name.replace('_parse', '_is_valid'))
                is_valid(*args)
                is_valid(0)
            finally:
                builtins.__import__ = real
            assert log == [], (fn_name, args, log)
    finally:
        sys.settrace(None)
    assert f_lines <= hits, sorted(f_lines - hits)


# ---- registry guard ----

def test_registry_guard_shape():
    tree = ast.parse(pathlib.Path(m.__file__).read_text())
    tries = [n for n in ast.walk(tree) if isinstance(n, ast.Try)]
    guard = [t for t in tries
             if any(isinstance(s, ast.ImportFrom) and s.module == REG
                    for s in t.body)]
    assert len(guard) == 1
    # the try body is EXACTLY the registry import: an inserted
    # statement (import os between try: and the import) dies here
    assert len(guard[0].body) == 1
    assert isinstance(guard[0].body[0], ast.ImportFrom)
    h = guard[0].handlers[0]
    # the handler body is EXACTLY the re-raise If plus the fallback
    # def, and the If body is exactly the bare raise: an inserted
    # statement at either level dies here
    assert len(h.body) == 2
    assert isinstance(h.body[0], ast.If)
    assert len(h.body[0].body) == 1
    assert isinstance(h.body[0].body[0], ast.Raise)
    assert isinstance(h.body[1], ast.FunctionDef)
    assert type(h.type) is ast.Name and h.type.id == 'ModuleNotFoundError'
    assert "'P235:%s:%s'" in ast.dump(h)


def test_registry_guard_reraises_foreign_import_error():
    # or->and at the registry fallback guard must die: a
    # ModuleNotFoundError naming a DIFFERENT module while the
    # registry is genuinely absent must propagate, not silently
    # fall back
    import builtins as _b
    import importlib.util as _iu
    real_import = _b.__import__
    real_find_spec = _iu.find_spec

    def bogus_import(name, *a, **k):
        if name.endswith('p235_concepts_registry'):
            raise ModuleNotFoundError(
                "No module named 'x.other'", name='x.other')
        return real_import(name, *a, **k)

    def no_spec(name, *k, **kw):
        if name.endswith('p235_concepts_registry'):
            return None
        return real_find_spec(name, *k, **kw)

    src = pathlib.Path(m.__file__).read_text()
    _b.__import__ = bogus_import
    _iu.find_spec = no_spec
    try:
        mod = types.ModuleType('fresh_b1191')
        with pytest.raises(ModuleNotFoundError):
            exec(compile(src, 'fresh_b1191', 'exec'), mod.__dict__)
    finally:
        _b.__import__ = real_import
        _iu.find_spec = real_find_spec


def test_registry_import_failure_modes_propagate():
    # except-ModuleNotFoundError is pinned: a registry that exists but
    # lacks make_fail, one that fails importing an inner dependency,
    # or one that raises ModuleNotFoundError naming the registry
    # itself must propagate rather than silently fall back.
    import subprocess
    mod_path = pathlib.Path(m.__file__).name
    src_text = pathlib.Path(m.__file__).read_text()
    reg_raise = ("raise ModuleNotFoundError('gone', "
                 "name=%r)\n" % REG)
    for body, exc_kind in (
            ('X = 1\n', 'ImportError'),
            ('import no_such_dep_xyz_1191\n', 'ModuleNotFoundError'),
            (reg_raise, 'ModuleNotFoundError')):
        with tempfile.TemporaryDirectory() as td:
            pkg = pathlib.Path(td) / 'app' / 'modules' / 'instinct_doc'
            pkg.mkdir(parents=True)
            (pkg.parent.parent / '__init__.py').write_text('')
            (pkg.parent / '__init__.py').write_text('')
            (pkg / 'p235_concepts_registry.py').write_text(body)
            (pkg / mod_path).write_text(src_text)
            code = ('import sys; sys.path.insert(0, %r); '
                    'import app.modules.instinct_doc.%s'
                    % (td, mod_path[:-3]))
            r = subprocess.run(
                [sys.executable, '-I', '-S', '-c',
                 'try:\n ' + code + '\nexcept ' + exc_kind +
                 ':\n print("ok")'],
                capture_output=True, text=True,
                env={'PATH': os.environ.get('PATH', '/usr/bin:/bin')})
            assert r.stdout.strip() == 'ok', (exc_kind, r.stderr[-300:])


def test_find_spec_called_with_exact_registry_name_once():
    # the import guard must probe find_spec with EXACTLY the registry
    # module name, exactly once, on the fallback path (a mutated
    # argument like REG + 'Z' dies here)
    import importlib.util as _iu
    src = pathlib.Path(m.__file__).read_text()
    calls = []
    real_import = builtins.__import__
    real_find_spec = _iu.find_spec

    def bogus_import(name, *a, **k):
        if name.endswith('p235_concepts_registry'):
            raise ModuleNotFoundError(
                "No module named %r" % REG, name=REG)
        return real_import(name, *a, **k)

    def spy_find_spec(name, *a, **k):
        calls.append(name)
        return None

    builtins.__import__ = bogus_import
    _iu.find_spec = spy_find_spec
    try:
        mod = types.ModuleType('fresh_b1191_spy')
        exec(compile(src, 'fresh_b1191_spy', 'exec'), mod.__dict__)
    finally:
        builtins.__import__ = real_import
        _iu.find_spec = real_find_spec
    assert calls == [REG], calls
    # the fallback engaged and works
    assert mod.websocket_frame_is_valid(b'\x81\x00') is True
    try:
        mod.make_fail('x')('c')
    except ValueError as e:
        assert str(e) == 'P235:x:c'
    else:
        raise AssertionError('fallback make_fail did not raise')


def test_battery_rev0_pins():
    # the second octet splits into MASK + 7-bit marker: a masked
    # 125-byte control frame is legal, 126-marker is not
    m.websocket_frame_parse(
        b'\x89\xfd' + _MASK_KEY + _mask(_MASK_KEY, b'p' * 125))
    refuse(FP, 'bad_value:control.length', b'\x89\xfe')
    # each RSV bit position individually (0x40/0x20/0x10)
    refuse(FP, 'bad_value:rsv.nonzero', b'\xc1\x00')
    refuse(FP, 'bad_value:rsv.nonzero', b'\xa1\x00')
    refuse(FP, 'bad_value:rsv.nonzero', b'\x91\x00')
    # opcode nibble boundary: 0xA pong legal, 0xB reserved
    m.websocket_frame_parse(b'\x8a\x00')
    refuse(FP, 'bad_value:opcode.reserved', b'\x8b\x00')
    # 7-bit marker boundary: 125 direct, 126 triggers the 16-bit form
    m.websocket_frame_parse(b'\x82\x7d' + b'd' * 125)
    refuse(FP, 'bad_value:frame.truncated.length16', b'\x82\x7e')
    # 16-bit form boundary: value 125 minimal-refuses, 126 accepts
    refuse(FP, 'bad_value:length.minimal', b'\x82\x7e\x00\x7d')
    m.websocket_frame_parse(b'\x82\x7e\x00\x7e' + b'd' * 126)
    # 64-bit form boundary: value 65535 minimal-refuses, 65536 accepts
    refuse(FP, 'bad_value:length.minimal',
           b'\x82\x7f\x00\x00\x00\x00\x00\x00\xff\xff')
    m.websocket_frame_parse(
        b'\x82\x7f\x00\x00\x00\x00\x00\x01\x00\x00'
        + b'd' * 65536)
    # close-code boundary: 999 refuses, 1000 accepts; 1015 refuses,
    # 1016 accepts
    refuse(FP, 'bad_value:close.code.range', b'\x88\x02\x03\xe7')
    m.websocket_frame_parse(b'\x88\x02\x03\xe8')
    refuse(FP, 'bad_value:close.code.reserved', b'\x88\x02\x03\xf7')
    m.websocket_frame_parse(b'\x88\x02\x03\xf8')
    # the UTF-8 check sees the reason ONLY: a code whose bytes are
    # non-ASCII passes with a clean ASCII reason
    m.websocket_frame_parse(b'\x88\x04\x1f\xffok')
    # bytes subclasses refuse with the type code
    refuse(FP, 'bad_type:data.type', _BytesSub(b'\x81\x00'))

__DOC__ = 'RFC 6455 "The WebSocket Protocol": the s5.2 base frame\nformat as a byte-level wire grammar (the FIN/RSV1-3/opcode\nfirst octet, the MASK bit, the 7/16/64-bit payload-length\nforms, the masking key and the payload), the s5.2 opcode\nregistry, the s5.5 control-frame constraints, and the\ns5.5.1 close-frame body with the s7.4 status-code rules,\nover one complete frame of Python bytes.  The opening\nhandshake (s4), message fragmentation sequencing (s5.4),\nextension negotiation (s9), subprotocols and the security\nconsiderations (s10) are out of scope.\n\nPublic API:\n\n  websocket_frame_parse(data, expect_mask=None) -> a dict:\n      \'fin\': the FIN bit as a bool,\n      \'opcode\': the 4-bit opcode as an int,\n      \'opcode_name\': one of "continuation", "text",\n          "binary", "close", "ping", "pong",\n      \'is_control\': True for the control opcodes 0x8-0xA,\n      \'masked\': the MASK bit as a bool,\n      \'masking_key\': the raw 4-byte masking key, or None\n          when MASK is 0,\n      \'payload_length\': the decoded payload length,\n      \'payload\': the payload bytes, UNMASKED per s5.3,\n      \'header_length\': the number of bytes before the\n          payload (base header + extended length + masking\n          key),\n      \'close_code\': the close status code as an int, or\n          None unless the frame is a Close carrying a body,\n      \'close_reason\': the decoded UTF-8 reason string, or\n          None unless the close body carries one.\n  websocket_frame_is_valid(data, expect_mask=None) ->\n      True iff websocket_frame_parse would succeed.\n\n  expect_mask pins the sender\'s role: True requires the\n  MASK bit set (s5.1: "a client MUST mask all frames that\n  it sends to the server"); False requires it clear (s5.1:\n  "A server MUST NOT mask any frames that it sends to the\n  client"); None accepts either bit (role-neutral).\n\nGrammar notes (verified against the RFC 6455 text): s5.2\ndefines the first octet as FIN, RSV1, RSV2, RSV3 and a\n4-bit opcode, and the second as MASK plus a 7-bit payload\nlength.  RSV1-3 "MUST be 0 unless an extension is\nnegotiated that defines meanings for non-zero values";\nextension negotiation is out of scope here, so any nonzero\nRSV bit refuses.  The defined opcodes: "%x0 denotes a\ncontinuation frame", "%x1 denotes a text frame", "%x2\ndenotes a binary frame", "%x3-7 are reserved for further\nnon-control frames", "%x8 denotes a connection close",\n"%x9 denotes a ping", "%xA denotes a pong", "%xB-F are\nreserved for further control frames"; "If an unknown\nopcode is received, the receiving endpoint MUST _Fail the\nWebSocket Connection_", so reserved opcodes refuse.  The\npayload length rules: "if 0-125, that is the payload\nlength.  If 126, the following 2 bytes interpreted as a\n16-bit unsigned integer are the payload length.  If 127,\nthe following 8 bytes interpreted as a 64-bit unsigned\ninteger (the most significant bit MUST be 0) are the\npayload length.  Multibyte length quantities are expressed\nin network byte order.  Note that in all cases, the\nminimal number of bytes MUST be used to encode the length,\nfor example, the length of a 124-byte-long string can\'t\nbe encoded as the sequence 126, 0, 124."  s5.5: "Control\nframes are identified by opcodes where the most\nsignificant bit of the opcode is 1" and "All control\nframes MUST have a payload length of 125 bytes or less\nand MUST NOT be fragmented."  The s5.3 unmask transform:\n"j = i MOD 4" and "transformed-octet-i = original-octet-i\nXOR masking-key-octet-j"; "The masking does not affect\nthe length of the "Payload data"."  s5.5.1 close body:\n"If there is a body, the first two bytes of the body MUST\nbe a 2-byte unsigned integer (in network byte order)\nrepresenting a status code with value /code/ defined in\nSection 7.4.  Following the 2-byte integer, the body MAY\ncontain UTF-8-encoded data with value /reason/"; a\none-byte body cannot hold the mandatory 2-byte code, so it\nrefuses.  s7.4.1: 1005, 1006 and 1015 each "is a reserved\nvalue and MUST NOT be set as a status code in a Close\ncontrol frame by an endpoint".  s7.4.2: "Status codes in\nthe range 0-999 are not used."  s8.1: "When an endpoint\nis to interpret a byte stream as UTF-8 but finds that the\nbyte stream is not, in fact, a valid UTF-8 stream, that\nendpoint MUST _Fail the WebSocket Connection_."\n\nProfile decisions (OURS, not from the RFC text):\n  - The expect_mask parameter and its role mapping; the\n    default None is role-neutral.\n  - Only the exact bytes type is accepted for the frame\n    and only the exact bool type for expect_mask;\n    subclasses refuse with the type code.\n  - Continuation frames and fragmented DATA frames pass\n    frame-level validation: the s5.4 sequencing rules (a\n    continuation must follow an unfinished message, a new\n    data frame must not start mid-message) are connection\n    state, not frame grammar.\n  - Text-frame payloads are NOT UTF-8-checked here: a\n    fragmented text message can split a multi-byte\n    sequence across frames (s5.4), and s8.1 binds when the\n    endpoint interprets the reassembled stream.  A close\n    reason cannot be fragmented (s5.5), so it IS checked.\n  - Close status codes: only 0-999 ("not used", s7.4.2)\n    and 1005/1006/1015 (explicit MUST NOT, s7.4.1)\n    refuse.  1004 is accepted: s7.4.1 marks it "Reserved.\n    The specific meaning might be defined in the future."\n    with no MUST NOT, unlike the three refused values.\n    Undefined codes in 1000-2999 and the 3000-3999 and\n    4000-4999 ranges are accepted per the s7.4.2\n    reservations; the text does not constrain 5000-65535.\n  - Bytes beyond the declared payload length refuse: the\n    function validates ONE complete frame, and the payload\n    length "is the length of the "Extension data" + the\n    length of the "Application data"", so trailing bytes\n    belong to another frame.\n  - Masking-key freshness and unpredictability (s5.3) are\n    not frame-validatable: any 4 bytes pass as a key.\n  - Size cap (OURS): _MAX_FRAME_LENGTH bytes for the whole\n    wire frame.\n\nRefusal order: bad_type:data.type before\nbad_type:expect_mask.type before everything else; then the\nframe length cap (bad_value:data.length),\nbad_value:frame.short, bad_value:rsv.nonzero,\nbad_value:opcode.reserved, the control rules\n(bad_value:control.fragmented before\nbad_value:control.length), bad_value:mask.mismatch, the\nextended-length field (bad_value:frame.truncated.length16\nor bad_value:frame.truncated.length64, then\nbad_value:length.msb for the 64-bit form, then\nbad_value:length.minimal),\nbad_value:frame.truncated.masking_key,\nbad_value:frame.truncated.payload before\nbad_value:frame.trailing, then the close-body rules\n(bad_value:close.body.short, bad_value:close.code.range\nbefore bad_value:close.code.reserved,\nbad_value:close.reason.utf8).\n\nErrata (18 records: 3 Verified, 5 Rejected, 4 Held for\nDocument Update, 6 Reported; none folded).  The Verified\nrecords touch the opening handshake, not the validated\nframe grammar: Verified EID 3433 (s11.3.2, Technical)\nconcerns Sec-WebSocket-Extensions multiplicity in HTTP\nresponses; Verified EID 3473 (s4.1, Editorial) rewords the\nclient connection-wait rule; Verified EID 3150 (s4.1,\nTechnical) corrects the Sec-WebSocket-Key example value\n"AQIDBAUGBwgJCgsMDQ4PEC==" to "AQIDBAUGBwgJCgsMDQ4PEA==".\nNoted, not folded: Reported EID 7262 (s5.5.1, Technical)\nwould change the close reason from "MAY contain\nUTF-8-encoded data" to data which "MUST be UTF-8-encoded";\nthis unit already enforces UTF-8 on the reason per s8.1,\nso both readings validate identically here.  Reported EID\n5288 (s5.2, Editorial) rewords the frame-masking-key ABNF;\nReported EID 4672 (s5.6, Technical), Reported EID 4919\n(s7.4.1, Technical), Reported EID 6997 (s4.3/9.1,\nTechnical) and Reported EID 7608 (s7.1.1, Technical) do\nnot change the validated grammar.  Held for Document\nUpdate EID 3227 (s7.4.1) rewords the 1011 description,\nHeld EID 3432 (s5.7) relabels an example, Held EID 4398\n(s4.1) and Held EID 5498 (s11.2) touch handshake material;\nnone folded.  Rejected EID 3912 (s5.2) proposed renaming\nframe-payload-length-63; the printed 63-bit grammar\nstands.  Rejected EIDs 3215 (s5.3), 4184 (s5.4), 5453\n(s4.1) and 8491 (s9.1) do not touch the validated grammar.\n'
