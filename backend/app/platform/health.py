from __future__ import annotations
from typing import Callable

def readiness(database_probe:Callable[[],bool],redis_probe:Callable[[],bool],migration_current:Callable[[],bool])->tuple[bool,dict[str,bool]]:
    checks={"database":bool(database_probe()),"redis":bool(redis_probe()),"migrations":bool(migration_current())}
    return all(checks.values()),checks
