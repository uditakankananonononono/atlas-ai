"""Opt-in combined startup for the tested otel+loki pair only.

Retains original trace/probe and JSON logging contracts. Config rendering and
startup wiring tests are not live ingestion acceptance. No new instrumentation
coverage, production retention or external sink claim.
"""
from . import telemetry_bootstrap as telemetry
from .logging_bootstrap import install_json_logging,connect_worker_logging,uvicorn_logging_config

def start_api(settings):
    import atexit,os,uvicorn
    from app.auth.context import require_tenant
    from app.workers.celery_app import celery_app
    provider=telemetry.build_provider(settings.service_name,telemetry.otlp_processor(settings.endpoint))
    telemetry.trace.set_tracer_provider(provider)
    atexit.register(provider.shutdown)
    from app.main import app
    tracer=provider.get_tracer('atlas.telemetry_bootstrap')
    if settings.probe_enabled:
        telemetry.register_probe_route(app,tracer=tracer,auth_dependency=require_tenant,
            send_task=lambda name,kwargs:celery_app.send_task(name,kwargs=kwargs))
    app.add_middleware(telemetry.TraceMiddleware,tracer=tracer)
    uvicorn.run(app,host='0.0.0.0',port=int(os.getenv('PORT','8080')),proxy_headers=True,
                log_config=uvicorn_logging_config())

def main(argv=None):
    import os,sys
    args=sys.argv[1:] if argv is None else argv
    if len(args)!=1 or args[0] not in telemetry.MODES:raise SystemExit('usage: stacked_observability_bootstrap {api|worker}')
    settings=telemetry.load_settings(args[0],os.environ)
    install_json_logging()
    if args[0]=='api':start_api(settings)
    else:
        connect_worker_logging()
        telemetry._start_worker(settings)
    return 0

if __name__=='__main__':raise SystemExit(main())
