"""Operator-local ASR setup. Does not fetch, copy or download model assets."""
import argparse
import json
import os
from pathlib import Path
from .offline_asr import ASRConfig, ASRError


def config_from_env(env=None):
    env = os.environ if env is None else env
    if env.get('ATLAS_ASR_ENABLED') != '1':
        return None
    directory = env.get('ATLAS_ASR_MODEL_DIR')
    if not directory:
        raise ASRError('local model directory required')
    config = ASRConfig(Path(directory), env.get('ATLAS_ASR_MODEL_SIZE', 'small'))
    config.identity()  # fail before provisioning or constructing a service
    return config


def main(argv=None):
    parser = argparse.ArgumentParser(description='Verify local ASR assets or provision a known-new M25 workspace.')
    parser.add_argument('--model-dir', required=True)
    parser.add_argument('--model-size', default='small', choices=['tiny','base','small','medium','large-v3'])
    parser.add_argument('--m25-root')
    parser.add_argument('--tenant')
    parser.add_argument('--owner')
    parser.add_argument('--known-new', action='store_true')
    args = parser.parse_args(argv)
    try:
        config = ASRConfig(Path(args.model_dir), args.model_size)
        identity = config.identity()
        provisioned = False
        if any((args.m25_root, args.tenant, args.owner, args.known_new)):
            if not all((args.m25_root, args.tenant, args.owner, args.known_new)):
                raise ValueError()
            from app.modules.m25_knowledge_copilot_training.service_factory import provision
            provision(args.m25_root, args.tenant, args.owner, known_new=True, asr_config=config)
            provisioned = True
        print(json.dumps({'model_identity': identity, 'assets_verified': True,
                          'm25_provisioned': provisioned, 'real_inference_verified': False,
                          'accuracy_verified': False}))
        return 0
    except (ASRError, ValueError, OSError):
        print(json.dumps({'error':'local ASR provisioning unavailable'}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
