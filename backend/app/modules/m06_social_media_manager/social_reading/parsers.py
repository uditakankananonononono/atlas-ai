"""HTML parsers for the LinkedIn pages read through the session bridge.

Parsers are pure functions over HTML (BeautifulSoup, already a dependency) so
they are fully unit-testable offline with saved fixtures. They degrade
gracefully: a page that does not match the expected shape returns what could
be parsed, never invented data.
"""
from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup


def parse_linkedin_connections(html: str) -> list[dict[str, Any]]:
    """Connection cards from linkedin.com/mynetwork/invite-connect/connections/."""
    soup = BeautifulSoup(html, "html.parser")
    people: list[dict[str, Any]] = []
    cards = soup.select("li.mn-connection-card") or soup.select("div.mn-connection-card")
    for card in cards:
        link = card.select_one("a.mn-connection-card__link") or card.select_one("a[href*='/in/']")
        href = str(link.get("href", "")) if link else ""
        handle = ""
        if "/in/" in href:
            handle = href.split("/in/", 1)[1].strip("/").split("/")[0].split("?")[0]
        name_el = card.select_one(".mn-connection-card__name") or card.select_one("span[dir='ltr']")
        occupation_el = card.select_one(".mn-connection-card__occupation")
        if not handle:
            continue
        people.append({
            "handle": handle,
            "display_name": name_el.get_text(strip=True) if name_el else "",
            "bio": occupation_el.get_text(strip=True) if occupation_el else "",
            "external_url": f"https://www.linkedin.com/in/{handle}/",
        })
    return people


def parse_linkedin_feed(html: str) -> list[dict[str, Any]]:
    """Posts from linkedin.com/feed/."""
    soup = BeautifulSoup(html, "html.parser")
    posts: list[dict[str, Any]] = []
    containers = soup.select("div.feed-shared-update-v2")
    for container in containers:
        urn = str(container.get("data-urn", ""))
        actor_el = container.select_one(".update-components-actor__name") or container.select_one(
            ".feed-shared-actor__name")
        text_el = container.select_one(".update-components-text") or container.select_one(
            ".feed-shared-inline-show-more-text")
        link_el = container.select_one("a[href*='/posts/']") or container.select_one(
            "a[href*='/activity/']")
        href = str(link_el.get("href", "")) if link_el else ""
        actor = actor_el.get_text(strip=True) if actor_el else ""
        text = text_el.get_text(" ", strip=True) if text_el else ""
        if not urn and not text:
            continue
        posts.append({
            "handle": actor,
            "external_id": urn or href or text[:80],
            "text": text[:2000],
            "source_url": href if href.startswith("http") else (f"https://www.linkedin.com{href}" if href else ""),
        })
    return posts
