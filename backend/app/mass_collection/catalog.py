"""Turn a downloaded Common Crawl warc.paths.gz into bounded source configs.

No discovery network calls; the operator chooses a crawl and reviews terms.
"""
import gzip
from pathlib import Path
import re
from .engine import Source, CollectionError


def commoncrawl_sources(path: Path | str, *, terms_accepted=False, max_files=100):
    if not 1 <= max_files <= 10_000:
        raise CollectionError('max_files must be 1..10000')
    result = []
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        while len(result) < max_files:
            line = f.readline(4097)
            if not line: break
            value = line.strip()
            if len(line)>4096 or not re.fullmatch(r'crawl-data/CC-MAIN-[A-Za-z0-9-]+/segments/[A-Za-z0-9._-]+/warc/[A-Za-z0-9._-]+\.warc\.gz', value):
                raise CollectionError('invalid Common Crawl relative WARC path')
            result.append(Source(url='https://data.commoncrawl.org/'+value, format='commoncrawl', license='unknown-per-page', terms_url='https://commoncrawl.org/terms-of-use', terms_accepted=terms_accepted, dataset=value.split('/')[1]))
    return result
