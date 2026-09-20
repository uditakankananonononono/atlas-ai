"""Config-selectable collector registry. Registry names are explicit allow-lists."""
from .community import RedditPublicCollector, GitHubTopicsCollector
from .open_access import OpenAccessCollector
from .discovery import InterestWebDiscoveryCollector
from .channels import DiscordBotCollector, GmailNewsletterCollector
from .research_news import ArxivCollector, BioMedRxivCollector, PubMedCollector, SemanticScholarCollector, FeedCollector, HackerNewsCollector, ProductHuntCollector
from .linkedin import PublicLinkedInCollector
from .contacts import ApolloPeopleCollector, HunterDomainCollector
from .scholarships import ScholarshipSiteCollector
from .social import ApifyInstagramCollector, BrightDataInstagramCollector, PublicInstagramCollector, PublicPinterestCollector, PinterestApiCollector, XApiCollector, YouTubeDataCollector

COLLECTORS = {
    "reddit_public": RedditPublicCollector,
    "github_topics": GitHubTopicsCollector,
    "open_access": OpenAccessCollector,
    "arxiv": ArxivCollector,
    "biorxiv_medrxiv": BioMedRxivCollector,
    "pubmed": PubMedCollector,
    "semantic_scholar": SemanticScholarCollector,
    "rss_atom": FeedCollector,
    "hacker_news": HackerNewsCollector,
    "product_hunt": ProductHuntCollector,
    "interest_web_discovery": InterestWebDiscoveryCollector,
    "public_scholarship_sites": ScholarshipSiteCollector,
    "public_linkedin": PublicLinkedInCollector,
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
