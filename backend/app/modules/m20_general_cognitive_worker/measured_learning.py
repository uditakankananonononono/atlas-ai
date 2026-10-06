"""Measured recall and weakness-targeted practice, never fabricated mastery.

Answers and scored attempts are explicit caller evidence. Matching is exact
normalized text, not semantic grading or a claim to assess free-form reasoning.
"""
from __future__ import annotations
import math
import re
from datetime import datetime,timedelta


def text(value,name):
    if not isinstance(value,str) or not value.strip():raise ValueError(name+' must be nonempty text')
    return value.strip()


def normalized(value):return re.sub(r'\s+',' ',text(value,'answer')).casefold()


def recall_practice(p):
    items=p.get('recall_items');attempts=p.get('recall_attempts',[])
    if not isinstance(items,list) or not items or not isinstance(attempts,list):raise ValueError('nonempty recall_items and attempt list required')
    catalog={}
    for item in items:
        ident=text(item.get('id'),'item id');question=text(item.get('question'),'question');answers=item.get('accepted_answers')
        if ident in catalog or not isinstance(answers,list) or not answers:raise ValueError('unique items and accepted answers required')
        catalog[ident]={'id':ident,'question':question,'accepted_answers':[normalized(a) for a in answers],'skill':text(item.get('skill'),'skill')}
    seen=set();results=[];skill_counts={};latest={}
    delay=p.get('retry_delay_minutes',60)
    if type(delay) is not int or not 1<=delay<=43200:raise ValueError('retry_delay_minutes must be integer in [1,43200]')
    for row in attempts:
        evidence=text(row.get('evidence_id'),'evidence id');item_id=row.get('item_id')
        if evidence in seen or item_id not in catalog:raise ValueError('unique attempt evidence and known item required')
        seen.add(evidence)
        if row.get('closed_book') is not True:raise ValueError('recall assessment requires declared closed-book attempt')
        try:at=datetime.fromisoformat(row['attempted_at'])
        except (ValueError,TypeError,KeyError) as exc:raise ValueError('ISO attempted_at required') from exc
        if at.tzinfo is None:raise ValueError('attempted_at needs timezone')
        if item_id in latest and at<latest[item_id]:raise ValueError('attempts must be chronological per item')
        latest[item_id]=at
        correct=normalized(row.get('response')) in catalog[item_id]['accepted_answers']
        confidence=row.get('confidence')
        if isinstance(confidence,bool) or not isinstance(confidence,(int,float)) or not math.isfinite(confidence) or not 0<=confidence<=1:raise ValueError('finite confidence in [0,1] required')
        skill=catalog[item_id]['skill'];counts=skill_counts.setdefault(skill,[0,0]);counts[0]+=1;counts[1]+=int(correct)
        result={'evidence_id':evidence,'item_id':item_id,'correct':correct,'brier_loss':(confidence-int(correct))**2,
                'feedback':{'accepted_answers':catalog[item_id]['accepted_answers'],'mismatch':not correct},
                'retry_due_at':(at+timedelta(minutes=delay)).isoformat() if not correct else None}
        results.append(result)
    observed={r['item_id'] for r in results}
    return {'results':results,'unattempted_items':[{'id':k,'question':v['question'],'skill':v['skill']} for k,v in catalog.items() if k not in observed],
            'correct':sum(r['correct'] for r in results),'attempt_count':len(results),
            'skill_scores':[{'skill':s,'attempts':n,'correct':c,'observed_accuracy':c/n} for s,(n,c) in sorted(skill_counts.items())],
            'boundary':'Exact normalized recall matching on supplied answer keys and declared closed-book attempts. No semantic essay grading, proof of closed-book behavior or inferred mastery. Retry timestamps are plan data, not scheduled notifications.'}


def deliberate_practice(p):
    records=p.get('scored_attempts');exercises=p.get('exercise_catalog')
    if not isinstance(records,list) or not records or not isinstance(exercises,list) or not exercises:raise ValueError('scored_attempts and exercise_catalog required')
    seen=set();groups={};feedback=[]
    for row in records:
        evidence=text(row.get('evidence_id'),'evidence id');skill=text(row.get('skill'),'skill')
        if evidence in seen or type(row.get('succeeded')) is not bool:raise ValueError('unique evidence and boolean succeeded required')
        seen.add(evidence);reason=text(row.get('feedback'),'specific feedback')
        groups.setdefault(skill,[]).append(row['succeeded']);feedback.append({'evidence_id':evidence,'skill':skill,'feedback':reason,'succeeded':row['succeeded']})
    scores=[{'skill':skill,'attempts':len(values),'observed_accuracy':sum(values)/len(values)} for skill,values in sorted(groups.items())]
    weakest=min(r['observed_accuracy'] for r in scores);targets=[r['skill'] for r in scores if r['observed_accuracy']==weakest]
    catalog=[];ids=set()
    for exercise in exercises:
        ident=text(exercise.get('id'),'exercise id');skill=text(exercise.get('skill'),'exercise skill')
        if ident in ids:raise ValueError('exercise ids must be unique')
        ids.add(ident);catalog.append({'id':ident,'skill':skill,'task':text(exercise.get('task'),'exercise task')})
    selected=[exercise for exercise in catalog if exercise['skill'] in targets]
    return {'target_subskills':targets,'observed_skill_scores':scores,'selected_exercises':selected,
            'missing_exercise_skills':[skill for skill in targets if not any(e['skill']==skill for e in selected)],
            'feedback':feedback,'boundary':'Targets lowest observed accuracy from supplied scored evidence, preserving ties. Sample difficulty/exposure differences are not adjusted; no latent-skill model, guaranteed improvement or invented exercises.'}
