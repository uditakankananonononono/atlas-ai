"""Non-science deliverable declarations and read-only local file measurement.

File hashes establish bytes only, never dataset reality, tool runs or SOTA.
"""
from __future__ import annotations
import copy
import hashlib
import ipaddress
import os
from pathlib import Path, PurePosixPath
import re
import stat
from urllib.parse import urlsplit


class ContractError(ValueError):
    pass


KINDS = ('dataset', 'tool', 'code', 'test', 'verification_script', 'formula', 'real_life_data', 'external_validation', 'benchmark_output')
FIELDS = {'project_id', 'domain', 'source_lines', 'repository', 'requested_targets', 'artifacts', 'benchmark'}


def _text(value):
    if not isinstance(value,str) or not value.strip() or len(value)>2000 or any(ord(c)<32 or ord(c)==127 for c in value):
        raise ContractError('Invalid text')


def _identifier(value):
    if not isinstance(value,str) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,99}',value):
        raise ContractError('Invalid identifier')


def validate_spec(spec: dict) -> dict:
    if not isinstance(spec,dict) or set(spec)!=FIELDS:raise ContractError('Unexpected spec fields')
    _identifier(spec['project_id'])
    if spec['domain'] not in ('software','non_science'):raise ContractError('Science outside scope')
    if not isinstance(spec['source_lines'],list) or not spec['source_lines']:raise ContractError('Source references required')
    for ref in spec['source_lines']:
        if not isinstance(ref,str) or not re.fullmatch(r'P\d+\|L\d+',ref):raise ContractError('Invalid source reference')
    _text(spec['repository'])
    raw_url=spec['repository']
    if any(c.isspace() for c in raw_url) or '\\' in raw_url:
        raise ContractError('Invalid declared repository URL')
    try:
        u=urlsplit(raw_url)
        host=u.hostname
        port=u.port
    except ValueError as exc:
        raise ContractError('Invalid declared repository URL') from exc
    if u.scheme!='https' or not host or u.username or u.password or u.query or u.fragment or (port is not None and not 1<=port<=65535) or u.netloc.endswith(':'):
        raise ContractError('Invalid declared repository URL')
    try:
        ipaddress.ip_address(host)
    except ValueError:
        labels=host.split('.')
        if len(host)>253 or any(not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?',label) for label in labels):
            raise ContractError('Invalid declared repository URL')
    targets=spec['requested_targets']
    if not isinstance(targets,dict) or set(targets)!={'datasets','project_tools','program_tools'}:raise ContractError('Invalid target schema')
    if any(type(n)is not int or not 0<=n<=1000000 for n in targets.values()):raise ContractError('Invalid requested target')
    rows=spec['artifacts']
    if not isinstance(rows,list) or len(rows)>10000:raise ContractError('Invalid artifact list')
    ids=set();paths=set()
    for row in rows:
        if not isinstance(row,dict) or set(row)!={'id','kind','path','sha256'}:raise ContractError('Invalid artifact schema')
        _identifier(row['id'])
        if row['kind'] not in KINDS:raise ContractError('Invalid artifact kind')
        _text(row['path']);p=PurePosixPath(row['path'])
        if p.is_absolute() or any(x in ('','.', '..') for x in row['path'].split('/')) or '\\' in row['path']:raise ContractError('Artifact must be a contained relative path')
        if not isinstance(row['sha256'],str) or not re.fullmatch(r'[a-f0-9]{64}',row['sha256']):raise ContractError('Invalid SHA256')
        if row['id'] in ids or row['path'] in paths:raise ContractError('Duplicate artifact id or path')
        ids.add(row['id']);paths.add(row['path'])
    benchmark=spec['benchmark']
    if benchmark is not None:
        if not isinstance(benchmark,dict) or set(benchmark)!={'comparator','metric','dataset_artifact_id','result_artifact_id','protocol'}:raise ContractError('Invalid declared benchmark metadata')
        for value in benchmark.values():_text(value)
        if benchmark['dataset_artifact_id'] not in ids or benchmark['result_artifact_id'] not in ids:raise ContractError('Unknown benchmark artifact reference')
    return copy.deepcopy(spec)


def _measure(root_fd, row, bound):
    """Linux dirfd/no-follow traversal; never open a symlink or special file."""
    parent=os.dup(root_fd)
    leaf=None
    try:
        parts=row['path'].split('/')
        for part in parts[:-1]:
            next_fd=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=parent)
            os.close(parent);parent=next_fd
        leaf=os.open(parts[-1],os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=parent)
        before=os.fstat(leaf)
        if not stat.S_ISREG(before.st_mode):return 'NOT_REGULAR_FILE',None,None
        if before.st_size==0:return 'EMPTY_FILE',None,None
        if before.st_size>bound:return 'TOO_LARGE',None,None
        digest=hashlib.sha256();total=0
        while True:
            chunk=os.read(leaf,min(65536,bound-total+1))
            if not chunk:break
            total+=len(chunk)
            if total>bound:return 'TOO_LARGE',None,None
            digest.update(chunk)
        after=os.fstat(leaf)
        if (before.st_size,before.st_mtime_ns,before.st_ctime_ns)!=(after.st_size,after.st_mtime_ns,after.st_ctime_ns) or total!=before.st_size:return 'CHANGED_DURING_READ',None,None
        sha=digest.hexdigest()
        if sha!=row['sha256']:return 'HASH_MISMATCH',None,None
        return 'FILE_HASH_MATCH',sha,(before.st_dev,before.st_ino)
    except OSError:
        return 'UNREADABLE_OR_UNSAFE',None,None
    finally:
        if leaf is not None:os.close(leaf)
        os.close(parent)


def check_deliverables(root: str | Path, spec: dict, *, max_file_bytes: int=10000000) -> dict:
    data=validate_spec(spec)
    if type(max_file_bytes)is not int or not 1<=max_file_bytes<=1000000000:raise ContractError('Invalid file byte limit')
    try:root_fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    except OSError as exc:raise ContractError('Root must be a readable nonsymlink directory') from exc
    counts={kind:0 for kind in KINDS};hashes=set();identities=set();results=[]
    try:
        for row in data['artifacts']:
            status,sha,identity=_measure(root_fd,row,max_file_bytes)
            if status=='FILE_HASH_MATCH':
                if sha in hashes or identity in identities:status='DUPLICATE_CONTENT'
                else:
                    hashes.add(sha);identities.add(identity);counts[row['kind']]+=1
            results.append({**row,'status':status})
    finally:os.close(root_fd)
    return {'project_id':data['project_id'],'source_lines':data['source_lines'],
            'declared_repository':data['repository'],'requested_targets':data['requested_targets'],
            'artifacts':results,'measured_artifact_count':sum(counts.values()),
            'measured_artifact_counts':counts,'benchmark_metadata':data['benchmark'],
            'repository_created':'UNVERIFIED','dataset_use':'UNVERIFIED',
            'real_life_data':'UNVERIFIED','tool_execution':'UNVERIFIED',
            'test_execution':'UNVERIFIED','external_validation':'UNVERIFIED',
            'benchmark_execution':'UNVERIFIED','sota':'UNVERIFIED',
            'doc_lines_fulfilled':False,
            'boundary':'Only contained regular-file bytes and hashes measured. Categories and benchmark metadata are caller declarations. Counts are artifacts, not datasets used or tools executed.'}
