"""Public social data through licensed providers or official APIs only."""
from __future__ import annotations
import os
from urllib.parse import quote
from .base import CollectionBatch, CollectedItem, HttpCollector


class PublicInstagramCollector(HttpCollector):
    """Free anonymous public-profile collector with conservative pacing.

    Uses Instaloader without a login. It cannot access private profiles and stops on
    throttling/challenges instead of rotating identities or evading controls.
    """
    async def collect(self, config: dict) -> CollectionBatch:
        import asyncio
        try:
            import instaloader
        except ImportError as exc:
            raise RuntimeError("install the optional instaloader dependency") from exc
        loader=instaloader.Instaloader(download_pictures=False,download_videos=False,download_video_thumbnails=False,download_geotags=False,download_comments=False,save_metadata=False,compress_json=False,quiet=True)
        delay=max(8.0,float(config.get("delay_seconds",12)))
        post_limit=min(25,max(1,int(config.get("posts_per_account",12))))
        items=[]
        for account in config.get("accounts",[]):
            try:
                profile=await asyncio.to_thread(instaloader.Profile.from_username,loader.context,account)
                count=0
                for post in await asyncio.to_thread(lambda: list(profile.get_posts())):
                    items.append(CollectedItem(f"https://www.instagram.com/p/{post.shortcode}/",str(post.mediaid),{"provider":"instaloader_anonymous","platform":"instagram","username":account,"shortcode":post.shortcode,"caption":post.caption,"taken_at":post.date_utc.isoformat(),"is_video":post.is_video,"likes":post.likes,"comments":post.comments}))
                    count+=1
                    if count >= post_limit: break
                await asyncio.sleep(delay)
            except Exception as exc:
                name=type(exc).__name__.lower()
                if "rate" in name or "challenge" in name or "login" in name:
                    raise RuntimeError(f"public Instagram collection stopped on throttle/challenge for {account}") from exc
                raise
        return CollectionBatch(items,len(config.get("accounts",[])),detail={"provider":"instaloader_anonymous","pacing_seconds":delay})

class ApifyInstagramCollector(HttpCollector):
    async def collect(self, config: dict) -> CollectionBatch:
        token = os.getenv(config.get("token_env", "APIFY_API_TOKEN"))
        if not token: raise RuntimeError("APIFY_API_TOKEN is not configured")
        actor = config.get("actor_id", "apify/instagram-profile-scraper")
        response = await self.client.post(
            f"https://api.apify.com/v2/acts/{quote(actor, safe='')}/run-sync-get-dataset-items",
            params={"token": token, "format": "json", "clean": "true"},
            json={"usernames": config.get("accounts", []), "resultsLimit": config.get("posts_per_account", 20)},
        )
        response.raise_for_status(); rows=response.json()
        items=[]
        for row in rows:
            username=row.get("username") or row.get("ownerUsername") or "unknown"
            external=str(row.get("id") or row.get("shortCode") or username)
            url=row.get("url") or row.get("profileUrl") or f"https://www.instagram.com/{username}/"
            items.append(CollectedItem(url, external, {"provider":"apify","platform":"instagram",**row}))
        return CollectionBatch(items, 1, detail={"provider":"apify","accounts":len(config.get("accounts", []))})

class BrightDataInstagramCollector(HttpCollector):
    async def collect(self, config: dict) -> CollectionBatch:
        token=os.getenv(config.get("token_env", "BRIGHT_DATA_API_TOKEN"))
        dataset=self.require(config,"dataset_id")
        if not token: raise RuntimeError("BRIGHT_DATA_API_TOKEN is not configured")
        inputs=[{"url":f"https://www.instagram.com/{name}/"} for name in config.get("accounts", [])]
        response=await self.client.post(
            "https://api.brightdata.com/datasets/v3/trigger",
            params={"dataset_id":dataset,"include_errors":"true"},
            headers={"Authorization":f"Bearer {token}"}, json=inputs,
        )
        response.raise_for_status(); data=response.json()
        # Trigger is asynchronous. Snapshot retrieval is scheduled after provider completion.
        return CollectionBatch([],1,cursor=data.get("snapshot_id"),detail={"provider":"bright_data","status":"triggered"})

class XApiCollector(HttpCollector):
    async def collect(self, config: dict) -> CollectionBatch:
        token=os.getenv(config.get("token_env","X_BEARER_TOKEN"))
        if not token: raise RuntimeError("X_BEARER_TOKEN is not configured")
        response=await self.client.get("https://api.x.com/2/tweets/search/recent",headers={"Authorization":f"Bearer {token}"},params={"query":self.require(config,"query"),"max_results":min(100,max(10,int(config.get("max_results",100)))),"tweet.fields":"created_at,author_id,entities,public_metrics"})
        response.raise_for_status(); data=response.json(); items=[]
        for row in data.get("data",[]):
            ident=str(row["id"]); items.append(CollectedItem(f"https://x.com/i/web/status/{ident}",ident,{"provider":"x_api","platform":"x",**row}))
        return CollectionBatch(items,1,cursor=data.get("meta",{}).get("next_token"),detail={"provider":"x_api"})

class YouTubeDataCollector(HttpCollector):
    async def collect(self, config: dict) -> CollectionBatch:
        key=os.getenv(config.get("key_env","YOUTUBE_API_KEY"))
        if not key: raise RuntimeError("YOUTUBE_API_KEY is not configured")
        response=await self.client.get("https://www.googleapis.com/youtube/v3/search",params={"key":key,"part":"snippet","q":self.require(config,"query"),"type":"video","maxResults":min(50,int(config.get("max_results",50))),"pageToken":config.get("cursor")})
        response.raise_for_status(); data=response.json(); items=[]
        for row in data.get("items",[]):
            video_id=row.get("id",{}).get("videoId")
            if video_id: items.append(CollectedItem(f"https://www.youtube.com/watch?v={video_id}",video_id,{"provider":"youtube_data_api","platform":"youtube",**row}))
        return CollectionBatch(items,1,cursor=data.get("nextPageToken"),detail={"provider":"youtube_data_api"})

class PinterestApiCollector(HttpCollector):
    """Pinterest API v5 boards/pins for an authorized standard-access app."""
    async def collect(self, config: dict) -> CollectionBatch:
        token=os.getenv(config.get("token_env","PINTEREST_ACCESS_TOKEN"))
        if not token: raise RuntimeError("PINTEREST_ACCESS_TOKEN is not configured")
        board_id=self.require(config,"board_id")
        response=await self.client.get(f"https://api.pinterest.com/v5/boards/{board_id}/pins",headers={"Authorization":f"Bearer {token}"},params={"page_size":min(100,int(config.get("page_size",100))),"bookmark":config.get("cursor")})
        response.raise_for_status(); data=response.json(); items=[]
        for row in data.get("items",[]):
            ident=str(row["id"]); link=row.get("link") or f"https://www.pinterest.com/pin/{ident}/"
            items.append(CollectedItem(link,ident,{"provider":"pinterest_api_v5","platform":"pinterest",**row}))
        return CollectionBatch(items,1,cursor=data.get("bookmark"),detail={"provider":"pinterest_api_v5","board_id":board_id})

class PublicPinterestCollector(HttpCollector):
    """Conservative free crawler for public Pinterest board pages only."""
    async def collect(self, config: dict) -> CollectionBatch:
        import asyncio, re
        from bs4 import BeautifulSoup
        delay=max(5.0,float(config.get("delay_seconds",8)))
        max_pins=min(50,max(1,int(config.get("pins_per_board",25))))
        items=[]; requests=0
        for board_url in config.get("board_urls",[]):
            if not board_url.startswith("https://www.pinterest."):
                raise ValueError("public Pinterest collector accepts pinterest board URLs only")
            response=await self.client.get(board_url,headers={"User-Agent":config.get("user_agent","AtlasPublicIndexer/1.0")})
            requests+=1
            if response.status_code in (403,429): raise RuntimeError("public Pinterest collection stopped on throttle/block")
            response.raise_for_status(); soup=BeautifulSoup(response.text,"html.parser"); seen=set()
            for anchor in soup.select('a[href*="/pin/"]'):
                match=re.search(r"/pin/(\d+)",anchor.get("href", ""))
                if not match or match.group(1) in seen: continue
                ident=match.group(1); seen.add(ident)
                url=f"https://www.pinterest.com/pin/{ident}/"
                text=" ".join(anchor.get_text(" ",strip=True).split())
                image=anchor.find("img")
                items.append(CollectedItem(url,ident,{"provider":"pinterest_public_board","platform":"pinterest","board_url":board_url,"title":text,"image_url":image.get("src") if image else None}))
                if len(seen)>=max_pins: break
            await asyncio.sleep(delay)
        return CollectionBatch(items,requests,detail={"provider":"pinterest_public_board","boards":len(config.get("board_urls",[])),"pacing_seconds":delay})
