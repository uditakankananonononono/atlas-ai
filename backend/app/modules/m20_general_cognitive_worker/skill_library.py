"""Procedural memory (spec 4.2.3): skills are compiled, versioned action
sequences stored for reuse, plus the skill-learning algorithm that spots
repeated successful patterns in episodic memory and proposes new skills.
"""
from __future__ import annotations

from collections import Counter

from .embeddings import tokenize
from .schemas import ActionRecord, Episode, Skill, SkillStatus


def _signature(actions: list[ActionRecord]) -> tuple[str, ...]:
    return tuple(a.tool for a in actions)


class SkillLibrary:
    """Versioned skill store with pattern-based skill learning."""

    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> Skill:
        existing = self.find_by_name(skill.name)
        if existing is not None:
            skill.version = existing.version + 1
            existing.status = SkillStatus.RETIRED
        skill.status = SkillStatus.ACTIVE
        self._skills[skill.id] = skill
        return skill

    def compile(
        self,
        name: str,
        goal_pattern: str,
        steps: list[ActionRecord],
        *,
        evidence: dict | None = None,
    ) -> Skill:
        return self.register(Skill(
            name=name, goal_pattern=goal_pattern, steps=steps,
            evidence=evidence or {},
        ))

    def find_by_name(self, name: str) -> Skill | None:
        candidates = [
            s for s in self._skills.values()
            if s.name == name and s.status == SkillStatus.ACTIVE
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda s: s.version)

    def match(self, goal: str, *, limit: int = 3) -> list[Skill]:
        """Keyword-pattern match of a goal against active skills."""
        goal_tokens = set(tokenize(goal))
        if not goal_tokens:
            return []
        scored = []
        for skill in self._skills.values():
            if skill.status != SkillStatus.ACTIVE:
                continue
            pattern_tokens = set(tokenize(skill.goal_pattern))
            if not pattern_tokens:
                continue
            overlap = len(goal_tokens & pattern_tokens) / len(goal_tokens | pattern_tokens)
            if overlap > 0.0:
                scored.append((overlap, skill))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [skill for _, skill in scored[:limit]]

    def retire(self, name: str) -> bool:
        retired = False
        for skill in self._skills.values():
            if skill.name == name and skill.status == SkillStatus.ACTIVE:
                skill.status = SkillStatus.RETIRED
                retired = True
        return retired

    def propose_from_episodes(
        self, episodes: list[Episode], *, min_occurrences: int = 2,
    ) -> list[Skill]:
        """Skill learning: find action-sequence patterns that repeat across
        successful episodes and propose them as new skills (status=proposed).
        A human (or the approval center) activates them.
        """
        counts: Counter[tuple[str, ...]] = Counter()
        examples: dict[tuple[str, ...], Episode] = {}
        for episode in episodes:
            if len(episode.actions) < 2:
                continue
            sig = _signature(episode.actions)
            counts[sig] += 1
            examples.setdefault(sig, episode)
        proposals: list[Skill] = []
        for sig, count in counts.items():
            if count < min_occurrences:
                continue
            name = " -> ".join(sig)
            already = any(
                s.name == name and s.status != SkillStatus.RETIRED
                for s in self._skills.values()
            )
            if already:
                continue
            example = examples[sig]
            skill = Skill(
                name=name,
                goal_pattern=example.goal,
                steps=example.actions,
                status=SkillStatus.PROPOSED,
                evidence={"occurrences": count, "example_episode_id": example.id},
            )
            self._skills[skill.id] = skill
            proposals.append(skill)
        return proposals

    def activate(self, skill_id: str) -> Skill:
        skill = self._skills[skill_id]
        skill.status = SkillStatus.ACTIVE
        return skill

    def list(self, *, status: SkillStatus | None = None) -> list[Skill]:
        return [
            s for s in self._skills.values()
            if status is None or s.status == status
        ]

    def __len__(self) -> int:
        return len(self._skills)
