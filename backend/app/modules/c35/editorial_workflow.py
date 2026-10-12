"""Natural-voice revision tracking for owner-authored application text.

No detector scoring, evasion, submission, or undisclosed service calls. The
PaperBleach public product is identified, but an API was not verified; edits
can be supplied from an owner-chosen editor and remain review-only.
"""
from difflib import unified_diff
from hashlib import sha256
from pydantic import BaseModel, Field

VENDOR_SOURCE = 'https://paperbleach.ai/'

class EditorialRevision(BaseModel):
    original: str = Field(min_length=1, max_length=20000)
    revised: str = Field(min_length=1, max_length=20000)
    source_reference: str = Field(min_length=1, max_length=240)
    editor: str = Field(min_length=1, max_length=120)


def revision_packet(data: EditorialRevision) -> dict:
    if any(not x.strip() for x in (data.original, data.revised, data.editor, data.source_reference)):
        raise ValueError('nonblank owner text, revision and provenance required')
    return {'original_sha256': sha256(data.original.encode()).hexdigest(),
            'revised_sha256': sha256(data.revised.encode()).hexdigest(),
            'diff': list(unified_diff(data.original.splitlines(), data.revised.splitlines(),
                                     fromfile='owner-original', tofile='review-revision', lineterm='')),
            'original': data.original, 'revised': data.revised,
            'editor': data.editor, 'source_reference': data.source_reference,
            'review_checks': ['meaning and facts unchanged', 'owner voice preserved',
                              'rules of target application followed', 'owner final review'],
            'vendor_public_source': VENDOR_SOURCE,
            'vendor_api_verified': False, 'service_called': False,
            'detector_evasion_performed': False, 'submission_authorized': False,
            'status': 'revision_pending_owner_review'}
