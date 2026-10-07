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
    async def csv_handler(arguments): return summarize_csv(arguments)
    registry.register(ToolSpec(name='csv_summary',description='Compute grouped numeric summaries from supplied CSV text',
        capabilities=['csv','summary','numeric','group'],risk=Risk.READ,max_retries=1,
        parameters={'type':'object','properties':{'csv_text':{'type':'string','minLength':1,'maxLength':64000},
            'value_column':{'type':'string','minLength':1},'group_column':{'type':'string','minLength':1}},
            'required':['csv_text','value_column'],'additionalProperties':False}),csv_handler)
