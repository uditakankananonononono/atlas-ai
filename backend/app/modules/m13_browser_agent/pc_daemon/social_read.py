"""Daemon-side social reads through the owner's own logged-in session.

Instagram follower/following lists and feeds are not exposed by any official
API for personal accounts, so the daemon reads them with instaloader, logged
in as the owner, on her own machine, at human speed. Any login failure,
challenge, or throttle stops the run and is reported as blocked - there is
no retry loop, no identity rotation, no evasion.
"""
from __future__ import annotations

import asyncio
from typing import Any

from ..session_bridge.protocol import BlockKind, PlatformBlocked

DEFAULT_POST_LIMIT = 20
MAX_POST_LIMIT = 50
DEFAULT_PROFILE_LIMIT = 200
MAX_PROFILE_LIMIT = 500


def _bounded(value: Any, default: int, ceiling: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(parsed, ceiling))


async def run_social_read(args: dict[str, Any]) -> dict[str, Any]:
    platform = str(args.get("platform", "")).lower()
    operation = str(args.get("op", "")).lower()
    if platform != "instagram":
        raise PlatformBlocked(BlockKind.POLICY,
                              f"daemon social reads support instagram only; got '{platform}'")
    if operation not in {"followers", "following", "feed"}:
        raise ValueError(f"unknown social read op: {operation}")
    return await asyncio.to_thread(_instagram_read, operation, args)


def _instagram_read(operation: str, args: dict[str, Any]) -> dict[str, Any]:
    try:
        import instaloader
    except ImportError as error:
        raise RuntimeError("instaloader is not installed on this PC; run: pip install instaloader") from error
    username = str(args.get("username", "")).strip()
    if not username:
        raise ValueError("username is required (the owner's own Instagram login)")
    loader = instaloader.Instaloader(
        download_pictures=False, download_videos=False, download_video_thumbnails=False,
        download_geotags=False, download_comments=False, save_metadata=False,
        compress_json=False, quiet=True, max_connection_attempts=1, request_timeout=30.0)
    try:
        loader.load_session_from_file(username)
    except FileNotFoundError as error:
        raise PlatformBlocked(
            BlockKind.LOGIN_WALL,
            "no saved Instagram session on this PC; log in once with: "
            "instaloader --login <your username> (this stores the session locally, it is never uploaded)") from error
    try:
        profile = instaloader.Profile.from_username(loader.context, username)
        if operation == "feed":
            return _read_feed(loader, profile, args)
        return _read_people(profile, operation, args)
    except instaloader.exceptions.LoginRequiredException as error:
        raise PlatformBlocked(BlockKind.LOGIN_WALL, "Instagram asked for a fresh login") from error
    except instaloader.exceptions.TooManyRequestsException as error:
        raise PlatformBlocked(BlockKind.RATE_LIMIT, "Instagram throttled the read; try again later") from error
    except instaloader.exceptions.ConnectionException as error:
        message = str(error).lower()
        if "challenge" in message or "checkpoint" in message:
            raise PlatformBlocked(BlockKind.CHALLENGE, "Instagram presented a challenge; open Instagram in the browser to clear it") from error
        raise


def _read_people(profile: Any, operation: str, args: dict[str, Any]) -> dict[str, Any]:
    limit = _bounded(args.get("limit"), DEFAULT_PROFILE_LIMIT, MAX_PROFILE_LIMIT)
    source = profile.get_followers() if operation == "followers" else profile.get_followees()
    people = []
    for person in source:
        people.append({"handle": person.username, "display_name": person.full_name,
                       "bio": person.biography, "external_url": f"https://www.instagram.com/{person.username}/",
                       "is_verified": bool(person.is_verified)})
        if len(people) >= limit:
            break
    return {"platform": "instagram", "op": operation, "account": profile.username,
            "people": people, "count": len(people), "truncated": len(people) >= limit,
            "url": f"https://www.instagram.com/{profile.username}/"}


def _read_feed(loader: Any, profile: Any, args: dict[str, Any]) -> dict[str, Any]:
    limit = _bounded(args.get("limit"), DEFAULT_POST_LIMIT, MAX_POST_LIMIT)
    posts = []
    for post in profile.get_posts():
        posts.append({"handle": profile.username, "shortcode": post.shortcode,
                      "caption": (post.caption or "")[:2000],
                      "taken_at": post.date_utc.isoformat(), "is_video": bool(post.is_video),
                      "likes": post.likes, "comments": post.comments,
                      "external_url": f"https://www.instagram.com/p/{post.shortcode}/"})
        if len(posts) >= limit:
            break
    return {"platform": "instagram", "op": "feed", "account": profile.username,
            "posts": posts, "count": len(posts), "truncated": len(posts) >= limit,
            "url": f"https://www.instagram.com/{profile.username}/"}
