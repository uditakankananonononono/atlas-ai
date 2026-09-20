"""Tests for the drafting compliance engine. Pure functions, no fixtures."""

from __future__ import annotations

from app.modules.m06_social_media_manager.compliance import (
    check_caption,
    check_format,
    count_hashtags,
    is_blocking,
    split_x_thread,
    validate_draft,
)


def test_instagram_caption_limit_blocks_overlong_copy():
    issues = check_caption("instagram", "x" * 2201)
    assert any(i.code == "caption_too_long" and i.severity == "error" for i in issues)
    assert is_blocking(issues)
    assert check_caption("instagram", "x" * 2200) == []


def test_linkedin_caption_limit():
    assert is_blocking(check_caption("linkedin", "x" * 3001))
    assert check_caption("linkedin", "x" * 3000) == []


def test_hashtag_caps_per_platform():
    tags = " ".join(f"#tag{i}" for i in range(31))
    assert is_blocking(check_caption("instagram", tags))
    tags6 = " ".join(f"#tag{i}" for i in range(6))
    assert is_blocking(check_caption("twitter", tags6))
    assert not is_blocking(check_caption("instagram", " ".join(f"#tag{i}" for i in range(30))))


def test_count_hashtags_ignores_non_tag_hashes():
    assert count_hashtags("#one text #two") == 2
    assert count_hashtags("C# is a language") == 0


def test_sponsored_content_requires_disclosure():
    issues = check_caption("instagram", "Love this serum!", sponsored=True)
    assert any(i.code == "missing_disclosure" and i.severity == "error" for i in issues)
    assert not is_blocking(check_caption("instagram", "Love this serum! #ad", sponsored=True))
    assert not is_blocking(check_caption("instagram", "Love this serum! Paid partnership with GlowCo", sponsored=True))
    assert not is_blocking(check_caption("instagram", "Love this serum!", sponsored=False))


def test_engagement_bait_and_superlatives_warn_without_blocking():
    issues = check_caption("tiktok", "Tag a friend and share this to win! World's best serum, guaranteed results")
    codes = {i.code for i in issues}
    assert "engagement_bait" in codes
    assert "unverifiable_claim" in codes
    assert not is_blocking(issues)


def test_instagram_link_in_caption_warns():
    issues = check_caption("instagram", "Read more https://example.com/post")
    assert any(i.code == "link_not_clickable" and i.severity == "warning" for i in issues)


def test_thread_split_fits_and_numbers_chunks():
    text = " ".join(["word"] * 300)  # 1499 chars
    chunks = split_x_thread(text)
    assert len(chunks) > 1
    assert all(len(chunk) <= 280 for chunk in chunks)
    assert chunks[0].endswith(f"1/{len(chunks)}")
    assert chunks[-1].endswith(f"{len(chunks)}/{len(chunks)}")
    # Content is preserved across chunks (modulo the numbering suffixes).
    joined = " ".join(chunks)
    for suffix in [f"{i}/{len(chunks)}" for i in range(1, len(chunks) + 1)]:
        joined = joined.replace(" " + suffix, "")
    assert joined.split() == text.split()


def test_thread_split_short_text_stays_single_chunk():
    assert split_x_thread("short post") == ["short post"]


def test_thread_split_hard_splits_overlong_word():
    chunks = split_x_thread("x" * 900)
    assert len(chunks) >= 4
    assert all(len(chunk) <= 280 for chunk in chunks)


def test_thread_chunk_cap_blocks_giant_threads():
    text = " ".join(["word"] * 2000)
    issues = validate_draft("twitter", "thread", text)
    assert any(i.code == "thread_too_long" and i.severity == "error" for i in issues)


def test_carousel_rules():
    assert is_blocking(check_format("twitter", "carousel", media_count=3))
    assert is_blocking(check_format("instagram", "carousel", media_count=11))
    assert is_blocking(check_format("instagram", "carousel", media_count=1))
    assert not is_blocking(check_format("instagram", "carousel", media_count=5, alt_texts=5))


def test_video_format_platform_support():
    assert is_blocking(check_format("linkedin", "video_script_60s", media_count=1))
    assert not is_blocking(check_format("tiktok", "video_script_60s", media_count=1))


def test_missing_alt_text_warns():
    issues = check_format("instagram", "image", media_count=2, alt_texts=1)
    assert any(i.code == "missing_alt_text" and i.severity == "warning" for i in issues)


def test_unknown_platform_is_an_error():
    assert is_blocking(check_caption("myspace", "hi"))
    assert is_blocking(check_format("myspace", "image"))
