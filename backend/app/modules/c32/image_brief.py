"""S2.5 / c32.image_brief - image-concept generator.

Source excerpt (verbatim): "generate some highly realistic images of this
with AI making it more girly".

Produces prompt briefs and style boards for her chosen image tool over
SUPPLIED concepts. Generates no images itself; every output is labeled
AI-generated; deceptive realism claims are refused. Stdlib only, offline,
deterministic.
"""
from __future__ import annotations

from app.modules.c30 import policy

PREFIX = "TREND"
STYLES = ("soft-pastel", "glossy-editorial", "cozy-handmade", "bold-pop")


def brief(concept):
    """Prompt brief + style board for one supplied concept."""
    if isinstance(concept, bool) or not isinstance(concept, dict):
        raise ValueError("TREND_REFUSED_BAD_TYPE:concept")
    if concept.get("claim_real") or concept.get("market_as_real"):
        raise ValueError("TREND_REFUSED_DECEPTIVE")
    subject = policy.clean_text(concept.get("subject"), PREFIX, "subject", 256)
    style = concept.get("style", "soft-pastel")
    if style not in STYLES:
        raise ValueError("TREND_REFUSED_BAD_STYLE:" + str(style)[:64])
    audience = concept.get("audience")
    if audience is not None:
        policy.clean_text(audience, PREFIX, "audience", 128)
    prompt = "%s product concept, %s style, high detail, clearly AI-generated" % (subject, style)
    return {"prompt": prompt,
            "style_board": {"style": style, "subject": subject,
                            "palette_note": "style-board guidance only",
                            "audience": audience},
            "labels": {"ai_generated": True, "no_deceptive_realism": True},
            "scope": policy.scope(
                ["prompt briefs", "style boards", "AI-generated labeling"],
                ["image generation itself", "realism claims in marketing"],
                "supplied concept text")}


def styles() -> tuple:
    return STYLES
