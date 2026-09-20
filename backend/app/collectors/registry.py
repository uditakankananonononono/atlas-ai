"""Config-selectable collector registry. Registry names are explicit allow-lists."""
from .channels import DiscordBotCollector, GmailNewsletterCollector
from .contacts import ApolloPeopleCollector, HunterDomainCollector
from .scholarships import ScholarshipSiteCollector
from .social import ApifyInstagramCollector, BrightDataInstagramCollector, PublicInstagramCollector, PublicPinterestCollector, PinterestApiCollector, XApiCollector, YouTubeDataCollector

COLLECTORS = {
    "public_scholarship_sites": ScholarshipSiteCollector,
    "public_instagram": PublicInstagramCollector,
    "public_pinterest": PublicPinterestCollector,
    "pinterest_api_v5": PinterestApiCollector,
    "apify_instagram": ApifyInstagramCollector,
    "bright_data_instagram": BrightDataInstagramCollector,
    "apollo_people": ApolloPeopleCollector,
    "hunter_domain": HunterDomainCollector,
    "gmail_newsletters": GmailNewsletterCollector,
    "discord_invited_bot": DiscordBotCollector,
    "x_api": XApiCollector,
    "youtube_data_api": YouTubeDataCollector,
}

def build_collector(name: str, **kwargs):
    try: collector=COLLECTORS[name]
    except KeyError as exc: raise ValueError(f"collector is not registered: {name}") from exc
    return collector(**kwargs)
