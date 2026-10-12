"""Pins for guards of the offline ASR adapter that the main suite left unasserted."""
from types import SimpleNamespace

import pytest

from app.ingest.offline_asr import ASRConfig, ASRError, OfflineWhisper, Transcript
from app.modules.m25_knowledge_copilot_training.service_factory import ServiceUnavailable, provision
from test_offline_asr import config, model, wav  # noqa: F401  (shared fixtures and helper)


def test_bytes_subclass_audio_refused_before_loading(config, model):
    class Sub(bytes):
        pass

    engine = OfflineWhisper(config)
    with pytest.raises(ASRError, match="audio size or type invalid"):
        engine.transcribe(Sub(wav()))
    assert model.loads == [] and model.calls == []
    assert engine.transcribe(bytes(wav())).text == "hello"


@pytest.mark.parametrize("start,end", [(True, 1.5), (False, 1.5), (0.0, True), (0, True), (0.5, True)])
def test_bool_segment_times_refused(config, model, start, end):
    # a 2 second clip, so a bool that were accepted as 0 or 1 would otherwise be a valid segment
    model.rows = [SimpleNamespace(start=start, end=end, text="hi")]
    with pytest.raises(ASRError, match="segment time invalid"):
        OfflineWhisper(config).transcribe(wav(2.0))


def test_int_segment_times_still_accepted(config, model):
    model.rows = [SimpleNamespace(start=0, end=1, text="hi")]
    out = OfflineWhisper(config).transcribe(wav(1.0))
    assert out.segments[0]["start_seconds"] == 0.0 and out.segments[0]["end_seconds"] == 1.0
    assert type(out.segments[0]["start_seconds"]) is float


def test_config_subclass_refused_unmeasured(config, model, monkeypatch):
    class Sub(ASRConfig):
        def identity(self):  # a subclass could report any identity
            raise AssertionError("identity of a refused subclass must not be computed")

    with pytest.raises(ASRError, match="ASR config required"):
        OfflineWhisper(Sub(config.model_dir))
    assert model.loads == []
    assert OfflineWhisper(ASRConfig(config.model_dir)).identity == config.identity()


def test_provenance_returns_copies_not_the_stored_segments(config, model):
    out = OfflineWhisper(config).transcribe(wav())
    before = [dict(s) for s in out.segments]
    prov = out.provenance()
    assert prov["segments"] == before
    assert prov["segments"] is not out.segments and type(prov["segments"]) is list
    assert prov["segments"][0] is not out.segments[0]
    prov["segments"][0]["text"] = "changed"
    prov["segments"].append({"text": "extra"})
    prov["language"] = "xx"
    assert [dict(s) for s in out.segments] == before
    assert out.text == "hello" and out.language == "en"
    again = out.provenance()
    assert again["segments"] == before and again["language"] == "en"
    assert isinstance(out, Transcript) and len(out.segments) == 1


def test_provision_refuses_custom_profile_with_asr_config(config, tmp_path):
    root = tmp_path / "root"
    root.mkdir(mode=0o700)
    with pytest.raises(ServiceUnavailable):
        provision(root, "t", "owner", known_new=True, allow_test_scratch=True, profile="custom", asr_config=config)
    assert list(root.iterdir()) == []
    provision(root, "t", "owner", known_new=True, allow_test_scratch=True, asr_config=config)
    assert list(root.iterdir()) != []
