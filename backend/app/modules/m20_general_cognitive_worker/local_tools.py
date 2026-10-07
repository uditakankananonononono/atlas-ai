"""Bounded offline tools over caller-supplied data. No external truth inferred."""
import csv
import io
import math
from .schemas import ToolSpec, Risk


def summarize_csv(arguments):
    text = arguments['csv_text']
    if len(text.encode('utf-8')) > 64000: raise ValueError('CSV exceeds64000bytes')
    reader = csv.reader(io.StringIO(text), strict=True)
    try: header = next(reader)
    except StopIteration: raise ValueError('CSV needs a header')
    if len(header) != len(set(header)) or not header or any(not h.strip() for h in header):
        raise ValueError('CSV requires unique nonempty headers')
    value_column = arguments['value_column']; group_column = arguments.get('group_column')
    if value_column not in header or (group_column is not None and group_column not in header):
        raise ValueError('requested column missing')
    vi = header.index(value_column); gi = header.index(group_column) if group_column is not None else None
    groups = {}; count = 0
    for row in reader:
        count += 1
        if count > 1000: raise ValueError('CSV exceeds1000data rows')
        if len(row) != len(header): raise ValueError(f'CSV row{count} column count mismatch')
        try: value = float(row[vi])
        except ValueError as exc: raise ValueError(f'CSV row{count} is not numeric') from exc
        if not math.isfinite(value): raise ValueError('CSV values must be finite')
        group = row[gi] if gi is not None else 'all'
        groups.setdefault(group, []).append(value)
        if len(groups) > 100: raise ValueError('CSV exceeds100groups')
    if not count: raise ValueError('CSV needs data rows')
    output = []
    for group, values in sorted(groups.items()):
        try: total = math.fsum(values)
        except OverflowError as exc: raise ValueError('CSV sum overflow') from exc
        if not math.isfinite(total): raise ValueError('CSV sum must be finite')
        output.append({'group':group,'count':len(values),'sum':total,'mean':total/len(values),
                       'min':min(values),'max':max(values)})
    return {'rows':count,'value_column':value_column,'group_column':group_column,'groups':output,
            'source_verified':False,'status':'supplied_csv_numeric_summary',
            'boundary':'Numeric summaries only; units, provenance and business meaning are caller supplied. No currency conversion or missing-value imputation.'}


def register_local_tools(registry):
    async def filter_handler(arguments): return filter_csv(arguments)
    registry.register(ToolSpec(name='csv_filter',description='Select rows and columns from supplied CSV using exact field matches',
        capabilities=['csv','filter','select','records'],risk=Risk.READ,max_retries=1,
        parameters={'type':'object','properties':{
            'csv_text':{'type':'string','minLength':1,'maxLength':32000},
            'where':{'type':'object','maxProperties':20,'additionalProperties':{'type':'string'}},
            'columns':{'type':'array','minItems':1,'maxItems':50,'uniqueItems':True,'items':{'type':'string','minLength':1}}},
            'required':['csv_text'],'additionalProperties':False}),filter_handler)
    async def reconcile_handler(arguments): return reconcile_csv(arguments)
    registry.register(ToolSpec(name='csv_reconcile',description='Compare two supplied CSV exports by exact unique keys and selected fields',
        capabilities=['csv','reconcile','compare','exports'],risk=Risk.READ,max_retries=1,
        parameters={'type':'object','properties':{
            'left_csv':{'type':'string','minLength':1,'maxLength':32000},
            'right_csv':{'type':'string','minLength':1,'maxLength':32000},
            'key_column':{'type':'string','minLength':1},
            'compare_columns':{'type':'array','minItems':1,'maxItems':20,'uniqueItems':True,'items':{'type':'string','minLength':1}}},
            'required':['left_csv','right_csv','key_column','compare_columns'],'additionalProperties':False}),reconcile_handler)
    async def csv_handler(arguments): return summarize_csv(arguments)
    registry.register(ToolSpec(name='csv_summary',description='Compute grouped numeric summaries from supplied CSV text',
        capabilities=['csv','summary','numeric','group'],risk=Risk.READ,max_retries=1,
        parameters={'type':'object','properties':{'csv_text':{'type':'string','minLength':1,'maxLength':64000},
            'value_column':{'type':'string','minLength':1},'group_column':{'type':'string','minLength':1}},
            'required':['csv_text','value_column'],'additionalProperties':False}),csv_handler)


def reconcile_csv(arguments):
    key = arguments['key_column']; columns = arguments['compare_columns']
    if not columns or len(columns) != len(set(columns)): raise ValueError('unique nonempty comparison columns required')
    def parse(text):
        if len(text.encode('utf-8')) > 32000: raise ValueError('CSV exceeds32000bytes per export')
        reader = csv.reader(io.StringIO(text), strict=True)
        try: header = next(reader)
        except StopIteration: raise ValueError('CSV needs header')
        if not header or len(header) != len(set(header)) or any(not name.strip() for name in header):
            raise ValueError('unique nonempty headers required')
        if any(name not in header for name in [key, *columns]): raise ValueError('requested column missing')
        records = {}
        for row in reader:
            if len(row) != len(header): raise ValueError('CSV row column count mismatch')
            record = dict(zip(header, row)); identity = record[key]
            if not identity.strip() or identity in records: raise ValueError('unique nonempty record keys required')
            records[identity] = record
            if len(records) > 500: raise ValueError('CSV exceeds500records per export')
        return records
    left, right = parse(arguments['left_csv']), parse(arguments['right_csv'])
    changed = []; unchanged = []
    for identity in sorted(left.keys() & right.keys()):
        fields = {name: {'left': left[identity][name], 'right': right[identity][name]}
                  for name in columns if left[identity][name] != right[identity][name]}
        if fields: changed.append({'key': identity, 'fields': fields})
        else: unchanged.append(identity)
    return {'left_count':len(left),'right_count':len(right),'left_only':sorted(left.keys()-right.keys()),
            'right_only':sorted(right.keys()-left.keys()),'changed':changed,'unchanged':unchanged,
            'source_verified':False,'status':'supplied_csv_exact_key_field_reconciliation',
            'boundary':'Exact raw string comparison on supplied unique keys and columns; no fuzzy matching, numeric normalization, source verification or external changes.'}


def filter_csv(arguments):
    text = arguments['csv_text']; where = arguments.get('where', {}); columns = arguments.get('columns')
    if len(text.encode('utf-8')) > 32000: raise ValueError('CSV exceeds32000bytes')
    reader = csv.reader(io.StringIO(text), strict=True)
    try: header = next(reader)
    except StopIteration: raise ValueError('CSV needs header')
    if not header or len(header) != len(set(header)) or any(not name.strip() for name in header):
        raise ValueError('unique nonempty headers required')
    columns = header if columns is None else columns
    if not columns or len(columns) != len(set(columns)) or any(c not in header for c in columns):
        raise ValueError('unique known projection columns required')
    if any(k not in header for k in where): raise ValueError('filter column missing')
    output = io.StringIO(); writer = csv.writer(output, lineterminator='\n'); writer.writerow(columns)
    count = matched = 0
    for row in reader:
        count += 1
        if count > 1000: raise ValueError('CSV exceeds1000data rows')
        if len(row) != len(header): raise ValueError('CSV row column count mismatch')
        record = dict(zip(header, row))
        if all(record[key] == value for key, value in where.items()):
            writer.writerow([record[column] for column in columns]); matched += 1
    return {'csv_text':output.getvalue(),'input_rows':count,'matched_rows':matched,'columns':columns,
            'source_verified':False,'status':'supplied_csv_exact_filter_projection',
            'boundary':'Exact raw string AND predicates and selected columns only; no inferred status, normalization or external effects.'}
