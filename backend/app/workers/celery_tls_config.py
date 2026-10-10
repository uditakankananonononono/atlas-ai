"""Opt-in worker TLS bootstrap; no change to the base Celery application.

Fleet-wide cert issuance/rotation across a real production deployment. mTLS is OPT-IN via the override, not default; no claim that the base deployment is encrypted.
"""
import os
from pathlib import Path
import ssl


def tls_settings() -> dict:
    if os.environ.get('ATLAS_MTLS_ENABLED') != '1':
        raise RuntimeError('TLS bootstrap requires explicit override enablement')
    folder = Path(os.environ['ATLAS_MTLS_DIR'])
    if not folder.is_absolute():
        raise ValueError('TLS directory must be absolute')
    settings = {'ssl_cert_reqs': ssl.CERT_REQUIRED, 'ssl_ca_certs': str(folder / 'ca.pem'),
                'ssl_certfile': str(folder / 'cert.pem'), 'ssl_keyfile': str(folder / 'key.pem'),
                'ssl_check_hostname': True}
    return {'broker_use_ssl': dict(settings), 'redis_backend_use_ssl': dict(settings)}


def main() -> None:
    # Set TLS before importing tasks or starting a worker. No target import at
    # module load; tests may inspect the settings without booting Celery.
    settings = tls_settings()
    from app.workers.celery_app import celery_app
    if not celery_app.conf.broker_url.startswith('rediss://') or not celery_app.conf.result_backend.startswith('rediss://'):
        raise RuntimeError('TLS bootstrap refuses non-TLS broker/backend URLs')
    celery_app.conf.update(**settings)
    celery_app.worker_main(['worker', '--loglevel=INFO'])


if __name__ == '__main__':
    main()
