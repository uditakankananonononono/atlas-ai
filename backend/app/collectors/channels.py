"""User-controlled channels: connected Gmail newsletters and invited Discord bots."""
from __future__ import annotations
import base64, os, re
from email import policy
from email.parser import BytesParser
from .base import CollectionBatch, CollectedItem, HttpCollector

class GmailNewsletterCollector(HttpCollector):
    async def collect(self, config: dict) -> CollectionBatch:
        token=os.getenv(config.get("token_env","GOOGLE_OAUTH_ACCESS_TOKEN"))
        if not token: raise RuntimeError("Google OAuth access token is not configured")
        headers={"Authorization":f"Bearer {token}"}; query=config.get("query","newer_than:7d (label:newsletters OR category:updates OR from:linkedin.com OR from:x.com OR from:twitter.com)")
        listing=await self.client.get("https://gmail.googleapis.com/gmail/v1/users/me/messages",headers=headers,params={"q":query,"maxResults":min(500,int(config.get("max_results",100))),"pageToken":config.get("cursor")})
        listing.raise_for_status(); data=listing.json(); items=[]; requests=1
        for stub in data.get("messages",[]):
            response=await self.client.get(f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{stub['id']}",headers=headers,params={"format":"raw"}); requests+=1; response.raise_for_status()
            raw=base64.urlsafe_b64decode(response.json()["raw"]+"==="); message=BytesParser(policy=policy.default).parsebytes(raw)
            body=message.get_body(preferencelist=("plain","html")); content=body.get_content() if body else ""
            sender=str(message.get("from") or "").lower(); subject=str(message.get("subject") or "")
            kind="creator_newsletter"
            if "linkedin" in sender: kind="linkedin_digest"
            elif any(host in sender for host in ("x.com","twitter.com")) or re.search(r"posts? you (?:may have )?missed",subject,re.I): kind="x_digest"
            links=[]
            if body and body.get_content_type() == "text/html":
                try:
                    from bs4 import BeautifulSoup
                    links=[a.get("href") for a in BeautifulSoup(content,"html.parser").select("a[href]") if a.get("href")]
                except Exception: links=[]
            else: links=re.findall(r"https?://[^\s<>]+",content)
            items.append(CollectedItem(f"gmail://message/{stub['id']}",stub["id"],{"provider":"gmail","channel_kind":kind,"subject":subject,"from":message.get("from"),"date":message.get("date"),"body":content,"links":links[:200]}))
        return CollectionBatch(items,requests,cursor=data.get("nextPageToken"),detail={"provider":"gmail","query":query})

class DiscordBotCollector(HttpCollector):
    async def collect(self, config: dict) -> CollectionBatch:
        token=os.getenv(config.get("token_env","DISCORD_BOT_TOKEN"))
        if not token: raise RuntimeError("DISCORD_BOT_TOKEN is not configured")
        headers={"Authorization":f"Bot {token}"}; items=[]; requests=0
        for channel_id in config.get("channel_ids",[]):
            response=await self.client.get(f"https://discord.com/api/v10/channels/{channel_id}/messages",headers=headers,params={"limit":min(100,int(config.get("limit",100))),"after":config.get("after")}); requests+=1; response.raise_for_status()
            for row in response.json():
                ident=str(row["id"]); items.append(CollectedItem(f"https://discord.com/channels/{config.get('guild_id','@me')}/{channel_id}/{ident}",ident,{"provider":"discord_invited_bot",**row}))
        return CollectionBatch(items,requests,detail={"provider":"discord_invited_bot","channels":len(config.get("channel_ids",[]))})
