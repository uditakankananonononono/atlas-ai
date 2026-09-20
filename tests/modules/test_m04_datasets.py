import hashlib
from app.modules.m04_research_scientist.datasets import CsvDatasetAdapter, DatasetDescriptor, DatasetLicense, DatasetPolicyError


def descriptor(payload, permitted=True):
    checksum = "sha256:" + hashlib.sha256(payload).hexdigest()
    return DatasetDescriptor("d", "https://data.example/d.csv", DatasetLicense("CC-BY", "https://license", permitted),
                             "2026-01-01T00:00:00Z", checksum, ("id", "value"))


def test_licensed_checksum_verified_csv():
    payload = b"id,value\n1,yes\n"
    assert CsvDatasetAdapter(descriptor(payload)).load(payload) == [{"id": "1", "value": "yes"}]


def test_unlicensed_or_modified_data_rejected():
    payload = b"id,value\n1,yes\n"
    for action in (lambda: CsvDatasetAdapter(descriptor(payload, False)),
                   lambda: CsvDatasetAdapter(descriptor(payload)).load(payload + b"2,no\n")):
        try:
            action()
        except DatasetPolicyError:
            pass
        else:
            raise AssertionError("dataset policy failure accepted")
