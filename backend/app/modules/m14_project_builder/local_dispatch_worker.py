"""Spawn-safe entrypoint: package initialization imports ORM exactly once."""
from .local_dispatch import main
if __name__=='__main__':main()
