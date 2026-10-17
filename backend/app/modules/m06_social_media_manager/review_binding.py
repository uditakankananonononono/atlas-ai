"""Immutable JSON review payload for one M06 publishing action, not a permit."""
from datetime import timezone
from copy import deepcopy
import json

def publish_snapshot(entry):
    moment=entry.publish_at
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError('publish_at requires an explicit timezone before review')
    return {'version':2,'publish_target':deepcopy(entry.publish_target),'plan_id':entry.plan_id,'platform':entry.platform.value,
            'format':entry.format,'text':entry.text,
            'publish_at':moment.astimezone(timezone.utc).isoformat(),
            'media_urls':list(entry.media_urls),'alt_texts':list(entry.alt_texts),
            'thread_chunks':list(entry.thread_chunks),'link':entry.link,
            'sponsored':entry.sponsored}

def review_matches(entry, payload):
    try:
        return (type(payload) is dict and type(payload.get('publish_snapshot')) is dict
                and json.dumps(payload['publish_snapshot'],sort_keys=True,allow_nan=False)==json.dumps(publish_snapshot(entry),sort_keys=True,allow_nan=False))
    except (ValueError,TypeError,AttributeError):
        return False


def snapshot_matches(snapshot, payload):
    try:
        return (type(payload) is dict and type(payload.get('publish_snapshot')) is dict
                and json.dumps(payload['publish_snapshot'],sort_keys=True,allow_nan=False)
                    == json.dumps(snapshot,sort_keys=True,allow_nan=False))
    except (ValueError,TypeError):
        return False
