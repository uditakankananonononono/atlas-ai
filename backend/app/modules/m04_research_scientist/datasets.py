from __future__ import annotations

import csv
import hashlib
import io
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Iterable, Iterator


@dataclass(frozen=True, slots=True)
class DatasetLicense:
    name: str
    url: str
    permits_research: bool
    requires_attribution: bool = True
    notes: str = ""


@dataclass(frozen=True, slots=True)
class DatasetDescriptor:
    dataset_id: str
    source_url: str
    license: DatasetLicense
    retrieved_at: str
    checksum: str
    schema: tuple[str, ...]


class DatasetPolicyError(ValueError):
    pass


class LegalDatasetAdapter(ABC):
    """Parse caller-provided bytes only after explicit license/provenance checks."""

    def __init__(self, descriptor: DatasetDescriptor) -> None:
        self.descriptor = descriptor
        if not descriptor.license.permits_research:
            raise DatasetPolicyError(f"license {descriptor.license.name!r} does not permit research")
        if not descriptor.source_url.startswith(("https://", "http://")):
            raise DatasetPolicyError("source URL must be HTTP(S)")

    def verify(self, payload: bytes) -> None:
        actual = "sha256:" + hashlib.sha256(payload).hexdigest()
        if actual != self.descriptor.checksum:
            raise DatasetPolicyError(f"checksum mismatch: expected {self.descriptor.checksum}, got {actual}")

    def load(self, payload: bytes) -> list[dict[str, Any]]:
        self.verify(payload)
        records = list(self.parse(payload))
        required = set(self.descriptor.schema)
        for index, record in enumerate(records):
            missing = required - set(record)
            if missing:
                raise DatasetPolicyError(f"record {index} missing fields: {sorted(missing)}")
        return records

    @abstractmethod
    def parse(self, payload: bytes) -> Iterable[dict[str, Any]]: ...


class CsvDatasetAdapter(LegalDatasetAdapter):
    def parse(self, payload: bytes) -> Iterable[dict[str, Any]]:
        try:
            text = payload.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise DatasetPolicyError("CSV must be UTF-8") from error
        return csv.DictReader(io.StringIO(text))


class JsonLinesDatasetAdapter(LegalDatasetAdapter):
    def parse(self, payload: bytes) -> Iterator[dict[str, Any]]:
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError as error:
            raise DatasetPolicyError("JSONL must be UTF-8") from error
        for line_number, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise DatasetPolicyError(f"JSONL line {line_number} is not an object")
            yield value
