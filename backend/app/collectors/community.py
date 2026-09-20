"""Free public community and developer discovery adapters."""
from __future__ import annotations
import os
from .base import CollectionBatch, CollectedItem, HttpCollector

class RedditPublicCollector(HttpCollector):
    async def collect(self, config: dict) -> CollectionBatch:
        items=[]; requests=0
        for subreddit in config.get("subreddits",["competitions","scholarships"]):
            response=await self.client.get(f"https://www.reddit.com/r/{subreddit}/new.json",params={"limit":min(100,int(config.get("limit",50)))},headers={"User-Agent":config.get("user_agent","AtlasPublicIndexer/1.0")}); requests+=1
            if response.status_code in (403,429): raise RuntimeError("Reddit collection stopped on block/throttle")
            response.raise_for_status()
            for child in response.json().get("data",{}).get("children",[]):
                row=child.get("data",{}); ident=str(row.get("id")); url=f"https://www.reddit.com{row.get('permalink','')}"
                items.append(CollectedItem(url,ident,{"provider":"reddit_public_json","subreddit":subreddit,**row}))
        return CollectionBatch(items,requests,detail={"provider":"reddit_public_json"})

class GitHubTopicsCollector(HttpCollector):
    async def collect(self, config: dict) -> CollectionBatch:
        token=os.getenv(config.get("token_env","GITHUB_TOKEN")); headers={"Accept":"application/vnd.github+json","User-Agent":"AtlasPublicIndexer/1.0"}
        if token: headers["Authorization"]=f"Bearer {token}"
        items=[]; requests=0
        for topic in config.get("topics",[]):
            response=await self.client.get("https://api.github.com/search/repositories",headers=headers,params={"q":f"topic:{topic}","sort":"updated","per_page":min(100,int(config.get("limit",50)))}); requests+=1
            if response.status_code in (403,429): raise RuntimeError("GitHub collection stopped on quota/block")
            response.raise_for_status()
            for row in response.json().get("items",[]):
                items.append(CollectedItem(row["html_url"],str(row["id"]),{"provider":"github_topics","topic":topic,**row}))
        return CollectionBatch(items,requests,detail={"provider":"github_topics"})
