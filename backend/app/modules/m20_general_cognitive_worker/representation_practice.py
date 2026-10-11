"""Symbolic representation mapping and invariant example validation."""
from .calibration_predictor import text

def records(value,label,*,minimum=0,maximum=64):
    if not isinstance(value,list)or not minimum<=len(value)<=maximum:raise ValueError(f'{label} requires{minimum}..{maximum} records')
    if any(not isinstance(row,dict)for row in value):raise ValueError(label+' requires objects')
    return value

def features(value,label):
    if not isinstance(value,dict)or len(value)>32:raise ValueError(label+' requires<=32 text features')
    for k,v in value.items():text(k,label);text(v,label)
    return dict(value)

def concepts(p):
    result={}
    for row in records(p.get('concepts'),'concepts',minimum=1):
        key=text(row.get('concept_id'),'concept_id');invariants=features(row.get('invariants'),'invariants');source=text(row.get('source'),'concept source')
        if key in result or not invariants:raise ValueError('unique concepts with nonempty invariants required')
        result[key]={'concept_id':key,'invariants':invariants,'source':source}
    return result

def dual_pack(p):
    definitions=concepts(p);verbal={};visual={}
    for field,output,description in [('verbal_propositions',verbal,'text'),('visual_elements',visual,'alt_text')]:
        for row in records(p.get(field),field):
            key=text(row.get('id'),'representation id');concept=text(row.get('concept_id'),'concept_id');props=features(row.get('features'),'features');source=text(row.get('source'),'representation source');label=text(row.get(description),description)
            if key in output or concept not in definitions:raise ValueError('unique representation IDs and known concepts required')
            output[key]={'id':key,'concept_id':concept,'features':props,'source':source,description:label}
    mappings=[];seen=set()
    for row in records(p.get('representation_mappings'),'representation_mappings',maximum=256):
        a=text(row.get('verbal_id'),'verbal_id');b=text(row.get('visual_id'),'visual_id');concept=text(row.get('concept_id'),'concept_id')
        if a not in verbal or b not in visual or concept not in definitions:raise ValueError('known representation/concept references required')
        if (a,b)in seen:raise ValueError('duplicate mapping pair')
        seen.add((a,b));v=verbal[a];w=visual[b];inv=definitions[concept]['invariants']
        if v['concept_id']!=concept or w['concept_id']!=concept:raise ValueError('mapping concept differs from representation concept')
        missing_v=sorted(set(inv)-set(v['features']));missing_w=sorted(set(inv)-set(w['features']))
        conflict=sorted({key for key in set(v['features'])&set(w['features'])if v['features'][key]!=w['features'][key]}|{key for key,val in inv.items()if key in v['features']and v['features'][key]!=val or key in w['features']and w['features'][key]!=val})
        mappings.append({'verbal_id':a,'visual_id':b,'concept_id':concept,'conflicting_features':conflict,'missing_verbal_invariants':missing_v,'missing_visual_invariants':missing_w,'valid':not(conflict or missing_v or missing_w)})
    reports=[]
    for key in sorted(definitions):
        vs=sorted(k for k,v in verbal.items()if v['concept_id']==key);ws=sorted(k for k,w in visual.items()if w['concept_id']==key);pairs=sorted([m['verbal_id'],m['visual_id']]for m in mappings if m['concept_id']==key)
        reports.append({'concept_id':key,'verbal_ids':vs,'visual_ids':ws,'mapped_pairs':pairs,'missing_verbal':not vs,'missing_visual':not ws,'missing_mapping':not pairs})
    unmapped_v=sorted(set(verbal)-{m['verbal_id']for m in mappings});unmapped_w=sorted(set(visual)-{m['visual_id']for m in mappings})
    valid=all(not(r['missing_verbal']or r['missing_visual']or r['missing_mapping'])for r in reports)and all(m['valid']for m in mappings)and not(unmapped_v or unmapped_w)
    return {'status':'validated'if valid else 'gaps_or_conflicts','valid':valid,'concepts':[definitions[k]for k in sorted(definitions)],'concept_reports':reports,'mapping_reports':sorted(mappings,key=lambda r:(r['concept_id'],r['verbal_id'],r['visual_id'])),'unmapped_verbal_ids':unmapped_v,'unmapped_visual_ids':unmapped_w,'verbal_provenance':[{'verbal_id':k,'text':verbal[k]['text'],'source':verbal[k]['source']}for k in sorted(verbal)],'visual_accessibility':[{'visual_id':k,'alt_text':visual[k]['alt_text'],'source':visual[k]['source']}for k in sorted(visual)],'source_truth_verified':False,'image_understanding_executed':False,'learning_improvement':None,'boundary':'Supplied symbolic concept/feature mappings only, with accessibility text and computed coverage/conflict checks. No image interpretation/generation or learning-effectiveness claim.'}

def example_pack(p):
    definitions=concepts(p);reports=[];seen=set()
    for row in records(p.get('example_items'),'example_items',minimum=1,maximum=256):
        key=text(row.get('example_id'),'example_id');concept=text(row.get('concept_id'),'concept_id');props=features(row.get('features'),'example features');source=text(row.get('source'),'example source');role=row.get('role');variants=row.get('variant_features')
        if key in seen or concept not in definitions:raise ValueError('unique example IDs and known concepts required')
        seen.add(key)
        if role not in ('example','counterexample'):raise ValueError('explicit example/counterexample role required')
        if not isinstance(variants,list)or len(variants)>32:raise ValueError('variant_features requires<=32 text keys')
        for name in variants:text(name,'variant feature')
        if len(set(variants))!=len(variants)or not set(variants)<=set(props)or set(variants)&set(definitions[concept]['invariants']):raise ValueError('unique present variants must not be invariant features')
        invariant=definitions[concept]['invariants'];missing=sorted(set(invariant)-set(props));violated=sorted(k for k,v in invariant.items()if k in props and props[k]!=v)
        valid=not missing and (not violated if role=='example'else bool(violated))
        reports.append({'example_id':key,'concept_id':concept,'role':role,'violated_invariants':violated,'missing_invariants':missing,'variant_features':sorted(variants),'valid':valid,'source':source})
    coverage=[]
    for key in sorted(definitions):
        positive=sorted(r['example_id']for r in reports if r['concept_id']==key and r['role']=='example'and r['valid']);negative=sorted(r['example_id']for r in reports if r['concept_id']==key and r['role']=='counterexample'and r['valid'])
        coverage.append({'concept_id':key,'valid_example_ids':positive,'valid_counterexample_ids':negative,'coverage_complete':bool(positive and negative)})
    valid=all(r['valid']for r in reports)and all(r['coverage_complete']for r in coverage)
    return {'status':'validated'if valid else 'gaps_or_conflicts','valid':valid,'concepts':[definitions[k]for k in sorted(definitions)],'concept_reports':coverage,'example_reports':reports,'source_truth_verified':False,'learning_improvement':None,'boundary':'Supplied symbolic invariant/example/counterexample checks only. Variants are declared non-invariant properties; no semantic classification or learning-effectiveness claim.'}
