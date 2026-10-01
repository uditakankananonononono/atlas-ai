"""Run with PYTHONPATH=backend python -m app.mass_collection."""
import argparse
from dataclasses import fields
import getpass
import hashlib
import json
import os
from pathlib import Path
import sys
import zlib
from .engine import Collector, Source, Limits, CollectionError, INGEST_ERRORS
from .credentials import CredentialStore


def main(argv=None):
    parser = argparse.ArgumentParser(description='Atlas local corpus collection (no paid services)')
    parser.add_argument('--root', default=os.getenv('ATLAS_COLLECTION_ROOT', './data/mass-collection'))
    parser.add_argument('--tenant', default='local')
    subs = parser.add_subparsers(dest='command', required=True)
    run = subs.add_parser('collect'); run.add_argument('config', type=Path)
    ingest = subs.add_parser('ingest'); ingest.add_argument('config', type=Path); ingest.add_argument('file', type=Path)
    subs.add_parser('export'); subs.add_parser('status'); subs.add_parser('stop')
    credential = subs.add_parser('credential')
    credential.add_argument('name'); credential.add_argument('origin')
    credential.add_argument('--confirm-own-account', action='store_true', required=True)
    args = parser.parse_args(argv)
    root = Path(args.root)/hashlib.sha256(args.tenant.encode()).hexdigest()
    try:
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if args.command=='credential':
            token = getpass.getpass('Own-account bearer token (not echoed): ')
            CredentialStore(root/'credentials.json', args.tenant).save(args.name, args.origin, token, owner_confirmed=args.confirm_own_account)
            result = {'saved': args.name}
        else:
            config = json.loads(args.config.read_text()) if args.command in ('collect', 'ingest') else {}
            limits = Limits(**config.get('limits', {}))
            sources = [Source(**s) for s in config.get('sources', [])]
            if args.command in ('collect', 'ingest') and (not sources or len(sources)>10_000):
                raise CollectionError('config requires between 1 and 10000 sources')
            if args.command=='ingest' and len(sources)!=1:
                raise CollectionError('ingest config requires exactly one source')
            credentials = CredentialStore(root/'credentials.json', args.tenant) if any(s.credential for s in sources) else None
            c = Collector(root, limits=limits, credentials=credentials)
            if args.command=='collect': result = [c.collect(s) for s in sources]
            elif args.command=='ingest': result = c.ingest_file(sources[0], args.file)
            elif args.command=='export': result = c.export()
            elif args.command=='stop': c.stop(); result = {'stopped': True}
            else: result = c.status()
        print(json.dumps(result, indent=2))
        return 0
    except (CollectionError, *INGEST_ERRORS) as exc:
        print(f'Collection stopped: {exc}', file=sys.stderr)
        return 1


if __name__=='__main__':
    raise SystemExit(main())
