from dataclasses import dataclass

@dataclass(frozen=True)
class Module:
    id: int
    slug: str
    name: str
    status: str = "stub"

MODULES = [
    Module(0, "approval-center", "Human Approval Center", "implemented"),
    Module(1, "opportunity-discovery", "Opportunity Discovery Engine"),
    Module(2, "competition-manager", "Competition Manager", "implemented"),
    Module(3, "grant-writer", "Grant & Fellowship Writer", "implemented"),
    Module(4, "research-scientist", "Research Scientist", "implemented"),
    Module(5, "outreach-manager", "Outreach Manager", "implemented"),
    Module(6, "social-media-manager", "Social Media Manager", "implemented"),
    Module(7, "brand-collaboration", "Brand Collaboration Manager"),
    Module(8, "startup-growth", "Startup Growth"),
    Module(9, "knowledge-workspace", "Knowledge Workspace"),
    Module(10, "email-assistant", "Email Assistant"),
    Module(11, "calendar-intelligence", "Calendar Intelligence"),
    Module(12, "ai-research-lab", "AI Research Lab"),
    Module(13, "browser-agent", "Browser Agent"),
    Module(14, "project-builder", "Project Builder"),
    Module(15, "document-generator", "Document Generator"),
    Module(16, "executive-dashboard", "Executive Dashboard"),
    Module(17, "narrative-architect", "Social Advice Compiler & College Essay Architect"),
    Module(18, "side-hustle-scraper", "Side Hustle & Knowledge Scraper"),
    Module(19, "idea-incubator", "Autonomous Idea Incubator"),
    Module(20, "general-cognitive-worker", "General Cognitive Worker"),
    Module(21, "claire", "Claire Personal Assistant / Idea Realisation Engine"),
]
BY_ID = {module.id: module for module in MODULES}
