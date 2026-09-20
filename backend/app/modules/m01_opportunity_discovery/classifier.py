"""Zero-shot DeBERTa eligibility classifier plus real-label fine-tuning gate."""
from dataclasses import dataclass
import os

@dataclass(frozen=True)
class EligibilityResult:
    label: str
    score: float
    model: str

class EligibilityClassifier:
    def __init__(self, model: str | None = None) -> None:
        self.model = model or os.getenv("ATLAS_ELIGIBILITY_MODEL", "MoritzLaurer/deberta-v3-large-zeroshot-v2.0")
        self._pipeline = None

    def classify(self, text: str, profile: str) -> EligibilityResult:
        if self._pipeline is None:
            from transformers import pipeline
            self._pipeline = pipeline("zero-shot-classification", model=self.model)
        output = self._pipeline(text, candidate_labels=["eligible", "ineligible", "unclear"], hypothesis_template=f"Given this applicant profile: {profile}. The applicant is {{}}.")
        return EligibilityResult(output["labels"][0], float(output["scores"][0]), self.model)

MIN_FINE_TUNE_LABELS = 500
MIN_PER_CLASS = 100

def fine_tune_ready(label_counts: dict[str, int]) -> bool:
    """Training activates only after enough real, reviewed labels accumulate."""
    return sum(label_counts.values()) >= MIN_FINE_TUNE_LABELS and all(label_counts.get(label, 0) >= MIN_PER_CLASS for label in ("eligible", "ineligible", "unclear"))
