# Atlas operational metrics

`/metrics` is disabled unless `ATLAS_METRICS_TOKEN` is set. It requires the
exact bearer token and intentionally uses a separate service credential from
owner OIDC. Keep it on the private network; never expose a metrics token in
Grafana, browser URLs, or public configuration. Prometheus reads that same
value from `/run/secrets/atlas_metrics_token` using the supplied scrape config.
The example target is the Compose API service `api:8080`; adjust it for your
private deployment. Provision secrets via your normal secret manager.

Import `deploy/grafana/dashboard.json` and create a Prometheus datasource with
UID `atlas-prometheus`. The API process emits its own request, provider and
process metrics. Multiple API replicas require separate scrape targets. This
is not a Celery multiprocess metric aggregation mechanism: queue lengths are
read directly from the shared broker. Queue depth excludes running tasks.
Broker read failures emit `atlas_celery_queue_scrape_success=0` and omit queue
values. Missing provider token usage stays absent, never estimated.

Provider attempts are measured at Atlas's shared-model adapter boundary.
Direct vendor calls outside that boundary are not covered. Provider names are
allowlisted; model names, tenant identifiers, prompts and replies are not
labels. Request labels use registered route templates, never request paths.

`alerts.yml` contains Prometheus rules only. No external notifications are
configured or sent. Connect an Alertmanager receiver separately after choosing
and approving the destination. Local verification does not establish hosted
Grafana, production deployment, or a live LLM/provider acceptance.
