"""Small, tenant-scoped status/control surface. Collection stays on the local CLI."""
import hashlib
import os
from pathlib import Path
from fastapi import APIRouter, Depends
from app.auth.context import TenantContext, require_tenant
from .engine import Collector

router = APIRouter(prefix='/mass-collection', tags=['mass-collection'])


def local_collector(context: TenantContext = Depends(require_tenant)):
    # Never interpret a caller-supplied tenant as a filesystem path.
    tenant = hashlib.sha256(context.tenant_id.encode()).hexdigest()
    return Collector(Path(os.getenv('ATLAS_COLLECTION_ROOT', './data/mass-collection'))/tenant)


@router.get('/status')
def status(collector: Collector = Depends(local_collector)):
    return collector.status()


@router.post('/stop')
def stop(collector: Collector = Depends(local_collector)):
    collector.stop()
    return {'stopped': True}
