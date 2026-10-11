"""Finite, pure supplied-input flag rules. No rollout or release authority."""
from __future__ import annotations
import hashlib
import json
import math

KINDS = {'bool', 'int', 'number', 'string'}
COMPARATORS = {'eq', 'ne', 'lt', 'le', 'gt', 'ge'}
MAX_INTEGER = 2**53 - 1

def _fail(code, path):
    raise ValueError('FLAG697_' + code + ': ' + path)

def _shape(value, required, optional, path):
    if type(value) is not dict or not required <= value.keys() or value.keys() - required - optional:
        _fail('SCHEMA', path)

def _id(value, path, limit=64):
    if type(value) is not str or not 1 <= len(value) <= limit or not value.strip() or any(0xD800 <= ord(c) <= 0xDFFF for c in value):
        _fail('ID', path)

def _typed(value, kind, path):
    valid = ((kind == 'bool' and type(value) is bool)
             or (kind == 'int' and type(value) is int and abs(value) <= MAX_INTEGER)
             or (kind == 'number' and type(value) in (int, float)
                 and abs(value) <= MAX_INTEGER and math.isfinite(value))
             or (kind == 'string' and type(value) is str and len(value) <= 256
                 and not any(0xD800 <= ord(c) <= 0xDFFF for c in value)))
    if not valid:
        _fail('TYPE', path)

def _condition(node, schema, path, depth=1, counter=None):
    if counter is None:
        counter = [0]
    counter[0] += 1
    if depth > 8 or counter[0] > 128:
        _fail('BOUND', path)
    if type(node) is not dict or type(node.get('op')) is not str:
        _fail('SCHEMA', path)
    op = node['op']
    if op in ('all', 'any'):
        _shape(node, {'op', 'args'}, set(), path)
        if type(node['args']) is not list or not 1 <= len(node['args']) <= 127:
            _fail('BOUND', path + '.args')
        for i, child in enumerate(node['args']):
            _condition(child, schema, path + '.args.' + str(i), depth + 1, counter)
    elif op == 'not':
        _shape(node, {'op', 'arg'}, set(), path)
        _condition(node['arg'], schema, path + '.arg', depth + 1, counter)
    elif op in COMPARATORS or op == 'bucket':
        _shape(node, {'op', 'field', 'seed', 'percent'} if op == 'bucket' else {'op', 'field', 'value'}, set(), path)
        field = node['field']
        if type(field) is not str or field not in schema:
            _fail('FIELD', path + '.field')
        kind = schema[field]
        if op == 'bucket':
            if type(node['percent']) is not int or not 0 <= node['percent'] <= 100:
                _fail('BUCKET', path + '.percent')
            _id(node['seed'], path + '.seed', 128)
            if kind != 'string':
                _fail('OPERATOR_TYPE', path)
        else:
            _typed(node['value'], kind, path + '.value')
            if op not in ('eq', 'ne') and kind not in ('int', 'number'):
                _fail('OPERATOR_TYPE', path)
    else:
        _fail('OPERATOR', path + '.op')

def _run(node, context):
    op = node['op']
    if op in ('all', 'any'):
        children = [_run(c, context) for c in node['args']]
        values = [v for v, _ in children]
        missing = set().union(*(m for _, m in children))
        if op == 'all':
            result = False if False in values else None if None in values else True
        else:
            result = True if True in values else None if None in values else False
        return result, missing
    if op == 'not':
        value, missing = _run(node['arg'], context)
        return (None if value is None else not value), missing
    field = node['field']
    if field not in context:
        return None, {field}
    left = context[field]
    if op == 'bucket':
        encoded = json.dumps([node['seed'], left], ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        score = int.from_bytes(hashlib.sha256(encoded).digest()[:8], 'big') % 10000
        return score < node['percent'] * 100, set()
    right = node['value']
    if op == 'eq': result = left == right
    elif op == 'ne': result = left != right
    elif op == 'lt': result = left < right
    elif op == 'le': result = left <= right
    elif op == 'gt': result = left > right
    else: result = left >= right
    return result, set()

def evaluate_flags697(data):
    """Validate entire request before evaluation; lowest integer priority wins."""
    _shape(data, {'context_schema', 'evaluation_context', 'flags'}, set(), 'request')
    schema, context, flags = data['context_schema'], data['evaluation_context'], data['flags']
    if type(schema) is not dict or len(schema) > 64 or type(context) is not dict:
        _fail('BOUND' if type(schema) is dict and len(schema) > 64 else 'SCHEMA', 'context')
    for field, kind in schema.items():
        _id(field, 'schema.field')
        if type(kind) is not str or kind not in KINDS:
            _fail('TYPE', 'schema.' + field)
    for field, value in context.items():
        if type(field) is not str or field not in schema:
            _fail('FIELD', 'context.field')
        _typed(value, schema[field], 'context.' + field)
    if type(flags) is not list or len(flags) > 32:
        _fail('BOUND', 'flags')
    names = set()
    for f in flags:
        _shape(f, {'name', 'source_id', 'default', 'rules'}, {'safe'}, 'flag')
        _id(f['name'], 'flag.name'); _id(f['source_id'], 'flag.source_id', 128)
        if f['name'] in names:
            _fail('DUPLICATE_FLAG', f['name'])
        names.add(f['name'])
        _typed(f['default'], 'bool', 'flag.default')
        if 'safe' in f:
            _typed(f['safe'], 'bool', 'flag.safe')
        if type(f['rules']) is not list or len(f['rules']) > 32:
            _fail('BOUND', 'flag.rules')
        ids, priorities = set(), set()
        for r in f['rules']:
            _shape(r, {'id', 'source_id', 'priority', 'value', 'condition'}, set(), 'rule')
            _id(r['id'], 'rule.id'); _id(r['source_id'], 'rule.source_id', 128)
            if r['id'] in ids:
                _fail('DUPLICATE_RULE', r['id'])
            ids.add(r['id'])
            if type(r['priority']) is not int or not 0 <= r['priority'] <= 1000000:
                _fail('PRIORITY', r['id'])
            if r['priority'] in priorities:
                _fail('DUPLICATE_PRIORITY', f['name'])
            priorities.add(r['priority'])
            _typed(r['value'], 'bool', 'rule.value')
            _condition(r['condition'], schema, 'rule.' + r['id'])
    rows = []
    for f in sorted(flags, key=lambda x: x['name']):
        trace, winner = [], None
        for r in sorted(f['rules'], key=lambda x: x['priority']):
            matched, missing = _run(r['condition'], context)
            trace.append({'rule_id': r['id'], 'source_id': r['source_id'], 'priority': r['priority'],
                          'matched': matched, 'missing_fields': sorted(missing)})
            if winner is None and matched is True:
                winner = r
        rows.append({'name': f['name'], 'source_id': f['source_id'],
                     'value': winner['value'] if winner is not None else f['default'],
                     'reason': 'matched_rule' if winner is not None else 'default_no_match',
                     'priority': winner['priority'] if winner is not None else None,
                     'matched_rule_id': winner['id'] if winner is not None else None,
                     'caller_diagnostic_safe': f.get('safe'), 'trace': trace})
    return {'flags': rows, 'status': 'supplied_flag_rules_evaluated', 'capability_executed': True,
            'evidence_verified': False, 'repository_behavior_verified': False, 'release_authorized': False,
            'boundary': 'Finite caller-supplied rules only; no rollout, network, persistence or deployment.'}
