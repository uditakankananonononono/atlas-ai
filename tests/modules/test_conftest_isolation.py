"""The lazy approval-DB isolation fixture must build exactly once even when 8 threads touch the default service first."""
import threading


def test_lazy_isolated_approval_service_builds_once_under_concurrent_first_touch():
    from app.modules.m00_approval_center import service as m00
    svc = m00._default_service
    assert svc.__class__.__name__ == "_LazyService", "isolation fixture not active"
    errors, results = [], []
    barrier = threading.Barrier(8)

    def touch():
        try:
            barrier.wait()
            results.append(svc._build())
        except Exception as error:  # pragma: no cover - the failure being tested
            errors.append(error)
    threads = [threading.Thread(target=touch) for _ in range(8)]
    [t.start() for t in threads]; [t.join() for t in threads]
    assert not errors and svc.builds == 1 and len({id(r) for r in results}) == 1
