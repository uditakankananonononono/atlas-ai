"""Run from repo with PYTHONPATH=backend; fixed local probe, no owner queue."""
import asyncio
from dataclasses import asdict
import json
import os
import sys
from app.modules.m21_claire.runtime.model_readiness import check_local_model
from instinct_models.providers import ProviderError


def main():
    try:
        result=asyncio.run(check_local_model(os.environ['ATLAS_CLAIRE_MODEL_PROVIDER'],
                os.environ['ATLAS_CLAIRE_MODEL_URL'],os.environ['ATLAS_CLAIRE_MODEL_NAME']))
    except (KeyError,ValueError,ProviderError):
        print(json.dumps({'status':'configuration_invalid','learned_model_verified':False,'acceptance_a_met':False}))
        return 2
    print(json.dumps(asdict(result)))
    return 0 if result.status=='protocol_answered' else 1


if __name__=='__main__':sys.exit(main())
