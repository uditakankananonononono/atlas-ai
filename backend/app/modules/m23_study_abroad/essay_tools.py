"""Student-authored essay discovery and coaching tools; never writes final prose."""
from collections import Counter


MAX_EMBED_ITEMS = 50


class EssayToolService:
    def __init__(self, matcher=None):
        self.matcher = matcher  # optional LocalEmbeddingMatcher; None keeps the token-overlap behaviour

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return {w.strip(".,:;!?()[]\"'").lower() for w in text.split() if len(w) > 3}

    @staticmethod
    def _values(item: dict) -> list[str]:
        """Bounded, type-safe 'values': a str becomes [str]; None/numbers/non-lists become []; list entries are
        kept only if str/int/float (as str), max 20 entries of 200 chars. (Previously None/123/mixed lists were a 500.)"""
        v = item.get("values", [])
        if isinstance(v, str):
            v = [v]
        if not isinstance(v, list):
            return []
        return [str(x)[:200] for x in v[:20] if isinstance(x, (str, int, float)) and not isinstance(x, bool)]

    def topic_finder(self, prompt: str, evidence: list[dict]) -> dict:
        prompt_terms = self._tokens(prompt)
        candidates = []
        for index, item in enumerate(evidence):
            description = str(item.get("description", "")).strip()
            if not description:
                continue
            terms = self._tokens(description + " " + " ".join(self._values(item)))
            overlap = sorted(prompt_terms & terms)
            candidates.append({"evidence_index": index, "label": item.get("label", f"Evidence {index + 1}"),
                               "prompt_connections": overlap,
                               "reflection_questions": ["What changed before and after this experience?",
                                                        "Which specific scene could you describe in your own words?",
                                                        "What does this reveal that the rest of your application does not?"]})
        match_mode, match_detail = "token_overlap_fallback", "no embedding matcher configured" if self.matcher is None else ""
        if self.matcher is not None and len(candidates) > MAX_EMBED_ITEMS:
            match_detail = f"more than {MAX_EMBED_ITEMS} evidence items; embedding skipped (bounded work)"
        elif self.matcher is not None and candidates:
            docs = [(str(evidence[c["evidence_index"]].get("description", "")) + " "
                     + " ".join(self._values(evidence[c["evidence_index"]])))[:2000] for c in candidates]
            scores = self.matcher.rank(prompt[:2000], docs)
            if scores is not None:
                for c, sc in zip(candidates, scores):
                    c["embedding_similarity"] = sc
                candidates.sort(key=lambda c: -c["embedding_similarity"])
                match_mode, match_detail = "embedding_local_model", ""
            else:
                match_detail = "no usable local embedding (unreachable, busy, slow or malformed); token overlap used"
        return {"candidates": candidates, "match_mode": match_mode, "match_detail": match_detail, "student_selects_topic": True,
                "generated_essay_prose": None}

    def outline(self, prompt: str, student_thesis: str, evidence: list[dict]) -> dict:
        labels = [x.get("label", f"Evidence {i + 1}") for i, x in enumerate(evidence) if x.get("description")]
        return {"prompt": prompt, "student_thesis": student_thesis,
                "sections": [{"purpose": "opening scene", "student_evidence_options": labels[:2]},
                             {"purpose": "choice, action, and consequence", "student_evidence_options": labels},
                             {"purpose": "reflection and prompt connection", "student_evidence_options": labels[-2:]}],
                "questions": ["Does each section earn its place?", "Where can reflection be more specific?"],
                "generated_essay_prose": None}

    def hook_coach(self, student_hook: str, evidence: list[str]) -> dict:
        supported = any(self._tokens(student_hook) & self._tokens(e) for e in evidence)
        abstract = sum(1 for x in ("passion", "dream", "always", "journey") if x in student_hook.lower())
        return {"supported_by_evidence": supported,
                "checks": {"starts_in_student_voice": bool(student_hook.strip()),
                           "uses_specific_detail": len(self._tokens(student_hook)) >= 5,
                           "abstract_language_count": abstract},
                "questions": ["Can you replace an abstract claim with a sensory or factual detail?",
                              "What tension or unanswered question makes the reader continue?"],
                "replacement_hook": None}

    def conclusion_coach(self, student_conclusion: str, thesis: str) -> dict:
        overlap = sorted(self._tokens(student_conclusion) & self._tokens(thesis))
        return {"thesis_connection_terms": overlap,
                "checks": {"connects_to_thesis": bool(overlap),
                           "introduces_new_claim": False,
                           "student_authored": True},
                "questions": ["What new understanding has the story earned?",
                              "Can the last sentence point forward without making an unsupported promise?"],
                "replacement_conclusion": None}

    def clarity_review(self, draft: str) -> dict:
        sentences = [x.strip() for x in draft.replace("!", ".").replace("?", ".").split(".") if x.strip()]
        repeated = [w for w, n in Counter(self._tokens(draft)).items() if n >= 4]
        long = [i + 1 for i, s in enumerate(sentences) if len(s.split()) > 35]
        return {"sentence_count": len(sentences), "long_sentence_numbers": long,
                "repeated_terms": sorted(repeated),
                "coaching_questions": ["Which sentence can be made more concrete?",
                                       "Does every claim trace to something you experienced?"],
                "revised_draft": None, "guardrail": "student-authored-final"}
