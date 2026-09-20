from dataclasses import dataclass
from app.core.providers import generate

@dataclass(frozen=True)
class ReviewRound:
    round_number: int
    provider: str
    model: str
    critique: str

@dataclass(frozen=True)
class CrossReviewResult:
    final_text: str
    rounds: list[ReviewRound]
    humanizer_model: str

async def cross_model_review(text: str, guidelines: str, rounds: int = 3) -> CrossReviewResult:
    """GPT/Claude/Gemini cross-review with bounded configurable rounds and a final humanizer pass."""
    if not 1 <= rounds <= 10:
        raise ValueError("rounds must be between 1 and 10")
    current = text
    history: list[ReviewRound] = []
    providers = ("openai", "anthropic", "gemini")
    for index in range(rounds):
        provider = providers[index % len(providers)]
        model, critique = await generate(
            "Critically review this application against the rules. Flag unsupported claims, eligibility risks, rubric gaps, and specific fixes.\n\nRULES:\n"
            + guidelines + "\n\nAPPLICATION:\n" + current,
            provider,
            None,
        )
        history.append(ReviewRound(index + 1, provider, model, critique))
        revise_model, current = await generate(
            "Revise the application using the critique. Preserve only verified facts and return only the revised text.\n\nAPPLICATION:\n"
            + current + "\n\nCRITIQUE:\n" + critique,
            "anthropic",
            None,
        )
    humanizer_model, final = await generate(
        "Edit for natural human voice without changing facts, adding activities, evading detection, or weakening rubric fit. Return only edited text.\n\n" + current,
        "openai",
        None,
    )
    return CrossReviewResult(final, history, humanizer_model)
