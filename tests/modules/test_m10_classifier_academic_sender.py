"""Native qualification tests for the M10 academic-sender regex candidate.

Runs the REAL RuleBasedClassifier in the repo's native pytest harness.
The false positives matter because PROFESSOR_REPLY is in ACTIONABLE_CATEGORIES,
so a misclassified machine receipt gets an LLM reply draft proposed to the
Approval Center.
"""
import pytest

from app.modules.m10_email_assistant.classifier import ClassifierInput, RuleBasedClassifier
from app.modules.m10_email_assistant.schemas import EmailCategory

PROF = EmailCategory.PROFESSOR_REPLY


def category(sender, subject, snippet="", labels=(), headers=None):
    return RuleBasedClassifier().classify(ClassifierInput(
        subject=subject, sender=sender, snippet=snippet,
        labels=list(labels), headers=headers or {})).category


@pytest.mark.parametrize("sender,subject", [
    ("Dropbox <no-reply@dropbox.com>", "Re: Your receipt"),
    ("Android <noreply@android.com>", "Re: Security alert"),
    ("Drip <hello@drip.email>", "Weekly update"),
    ("Acme <profile-updates@acme.com>", "Your profile"),
    ("Drive <drive-shares-dm-noreply@example.com>", "Re: shared file"),
])
def test_substring_lookalikes_are_not_academic(sender, subject):
    assert category(sender, subject) != PROF


@pytest.mark.parametrize("sender,subject,expected", [
    ("Dr. Rao <rao@gmail.com>", "Re: your paper", PROF),
    ("Dr Sharma <sharma@hospital.org>", "Seminar invite", PROF),
    ("Prof. Iyer <iyer@gmail.com>", "Re: meeting", PROF),
    ("smith@stanford.edu", "Re: hi", PROF),
    ("rao@iitb.ac.in", "Question", PROF),
    ("MIT University <news@mit.example>", "Open day", PROF),
])
def test_title_tokens_and_academic_domains_still_match(sender, subject, expected):
    assert category(sender, subject) == expected


def test_professor_substring_localpart_no_longer_a_signal():
    # Explicitly changed behavior under the title-token policy: the academic
    # signal is now title tokens ("prof"/"dr" not followed by another letter)
    # plus .edu/.ac./university/college/institute. A bare "professor."
    # substring in the local part is not a title token, so this sender loses
    # the academic signal it had under the old substring regex and falls back
    # to PERSONAL (no reply draft proposed). Contract basis: the candidate's
    # grounded title-token policy; no test, doc, or other module in the repo
    # relies on the old substring behavior. This pin records the change; it is
    # not a claim of universal academic-sender accuracy.
    assert category("professor.rao@gmail.com", "Re: your paper") == EmailCategory.PERSONAL


def test_existing_contract_prof_at_edu_unchanged():
    assert category("prof@stanford.edu", "Re: your research question") == PROF


def test_precedence_spam_and_action_required_unchanged():
    assert category("Dr. Rao <rao@gmail.com>", "Re: paper", labels=["SPAM"]) == EmailCategory.SPAM
    assert category("Dr. Rao <rao@gmail.com>", "Action required: sign") == EmailCategory.ACTION_REQUIRED
