S = "backend/app/modules/m22_tools_hub/sources.py"
G = "backend/app/modules/m22_tools_hub/collectors.py"
T = "tests/modules/test_m22_source_collectors.py tests/modules/test_m22_phase2_features.py tests/modules/test_m22_row55_deepening.py"
MUT = [
 ("M1 devto query tag not slugged", 55, S, 'return self.url_template.format(query=quote_plus(query), tag=_tag_slug(query))', 'return self.url_template.format(query=quote_plus(query), tag=query)', T),
 ("M2 tag slug length cap removed", 55, S, 'return re.sub(r"[^a-z0-9]", "", query.lower())[:40]', 'return re.sub(r"[^a-z0-9]", "", query.lower())', T),
 ("M3 query not URL-quoted", 55, S, 'self.url_template.format(query=quote_plus(query)', 'self.url_template.format(query=query', T),
 ("M4 non-JSON body swallowed", 55, S, 'raise SourceError(f"{self.name} returned non-JSON content: {exc}") from exc', 'return', T),
 ("M5 kind overwritten by constant", 55, S, 'item.setdefault("kind", self.kind)', 'item["kind"] = "blog"', T),
 ("M6 devto result cap raised", 55, S, 'for x in (payload if isinstance(payload, list) else [])[:20]:\n        user = x.get("user") or {}', 'for x in (payload if isinstance(payload, list) else [])[:200]:\n        user = x.get("user") or {}', T),
 ("M7 devto summary not truncated", 55, S, '"summary": _truncate(_strip_html(x.get("description") or "")),\n            "version": None, "license": None,\n            "maintenance": 0.6, "security": 0.55', '"summary": _strip_html(x.get("description") or ""),\n            "version": None, "license": None,\n            "maintenance": 0.6, "security": 0.55', T),
 ("M8 devto html not stripped", 55, S, '"summary": _truncate(_strip_html(x.get("description") or "")),\n            "version": None, "license": None,\n            "maintenance": 0.6, "security": 0.55', '"summary": _truncate(x.get("description") or ""),\n            "version": None, "license": None,\n            "maintenance": 0.6, "security": 0.55', T),
 ("M9 wordpress title html not stripped", 55, S, '"name": _strip_html(x.get("title") or "") or "(untitled)",\n            "url": x.get("URL")', '"name": (x.get("title") or "") or "(untitled)",\n            "url": x.get("URL")', T),
 ("M10 hackernews self-post fallback url dropped", 55, S, 'url = x.get("url") or f"https://news.ycombinator.com/item?id={x.get(\'objectID\')}"', 'url = x.get("url") or ""', T),
 ("M11 itunes podcasts genre not filtered", 55, S, 'genres = [g for g in (x.get("genres") or []) if g.lower() != "podcasts"]', 'genres = [g for g in (x.get("genres") or [])]', T),
 ("M12 itunes result cap raised", 55, S, 'for x in (payload.get("results") if isinstance(payload, dict) else [])[:20]:\n        artist = x.get("artistName")', 'for x in (payload.get("results") if isinstance(payload, dict) else [])[:200]:\n        artist = x.get("artistName")', T),
 ("M13 itunes url prefers track url", 55, S, '"url": x.get("collectionViewUrl") or x.get("trackViewUrl") or "",', '"url": x.get("trackViewUrl") or x.get("collectionViewUrl") or "",', T),
 ("M14 itunes artist fallback removed", 55, S, 'artist = x.get("artistName") or "unknown artist"\n        genres', 'artist = x.get("artistName")\n        genres', T),
 ("M15 recency windows widened", 55, S, 'if days <= 180:\n        return 0.8', 'if days <= 1800:\n        return 0.8', T),
 ("M16 recency missing timestamp scored high", 55, S, 'if not timestamp:\n        return 0.5', 'if not timestamp:\n        return 0.8', T),
 ("M17 json size cap check removed", 55, S, 'if len(data) > limit:\n        if truncate_ok:', 'if False:\n        if truncate_ok:', T),
 ("M18 github repo cap raised", 55, G, "for x in p.get('items',[])[:20]:yield {'name':x['full_name']", "for x in p.get('items',[])[:200]:yield {'name':x['full_name']", T),
 ("M19 github url uses api url", 55, G, "'url':x['html_url']", "'url':x.get('url','')", T),
 ("M20 collector registry loses source group", 55, G, "return base+default_source_collectors()", "return base", T),
 ("M21 default sources drop the podcast", 55, S, 'JsonSourceCollector("itunes", "podcast", "https://itunes.apple.com/search?media=podcast&term={query}&limit=20", _parse_itunes),\n', '', T),
 ("M22 default sources drop devto", 55, S, 'JsonSourceCollector("devto", "blog", "https://dev.to/api/articles?tag={tag}&per_page=20&top=30", _parse_devto),\n', '', T),
]
