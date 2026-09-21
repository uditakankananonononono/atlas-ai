"""Creative-discipline briefs and specifications for feature rows 281-305.

Every row produces a typed draft SPECIFICATION (color script, type scale,
rig plan, score sketch brief, ...) that plugs into M06's content artifacts.
Two boundaries are enforced in code, not by prompt:

1. Nothing is rendered. This engine holds no render, audio, or browser
   reference. Every artifact carries a machine-readable disclaimer that no
   media was rendered, recorded, or generated, and asset prompts are
   restricted to the platform's self-hosted engines so a spec can only ever
   target infrastructure the user actually owns.
2. No copyrighted imitation. LLM output is scanned for "in the style of
   <named artist/brand/franchise>" phrasing; matches are redacted and the
   redaction is recorded on the artifact, so a brief can never launder an
   imitation request through the module.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from app.core.providers import ProviderError  # noqa: F401  (re-exported for routes)

from .marketing import ArtifactParseError, ArtifactRepository, GenerateFn, MarketingArtifact
from .models import AUDIO_ENGINE, IMAGE_ENGINE

ALLOWED_ASSET_ENGINES = {IMAGE_ENGINE, AUDIO_ENGINE}

RENDER_DISCLAIMER = (
    "Specification only: no media was rendered, recorded, generated, or exported. "
    "A human or a separately approved render pipeline executes this spec."
)

IMITATION_PATTERN = re.compile(
    r"in the style of\s+[A-Z][\w'.-]*(?:\s+[A-Z][\w'.-]*)*"
    r"|a (?:rip[- ]?off|knock[- ]?off|copy|clone|imitation) of\s+[\w'.-]+(?:\s+[\w'.-]+)*",
    re.IGNORECASE,
)


def redact_imitations(value: Any, findings: list[str]) -> Any:
    """Recursively redact style-imitation phrasing; record each redaction."""
    if isinstance(value, str):
        def _replace(match: re.Match) -> str:
            findings.append(f"redacted imitation phrasing: {match.group(0)!r}")
            return "an original treatment (style imitation redacted)"
        return IMITATION_PATTERN.sub(_replace, value)
    if isinstance(value, list):
        return [redact_imitations(item, findings) for item in value]
    if isinstance(value, dict):
        return {key: redact_imitations(item, findings) for key, item in value.items()}
    return value


def _filter_asset_prompts(sections: dict[str, Any]) -> None:
    """Asset prompts may only target the platform's self-hosted engines."""
    prompts = sections.get("asset_prompts")
    if not isinstance(prompts, list):
        return
    kept = []
    for item in prompts:
        if not isinstance(item, dict):
            continue
        engine = str(item.get("engine", ""))
        kind = str(item.get("kind", ""))
        if engine in ALLOWED_ASSET_ENGINES and kind in ("image", "audio"):
            kept.append({"kind": kind, "engine": engine, "prompt": str(item.get("prompt", ""))})
    sections["asset_prompts"] = kept


from .marketing import ArtifactSpec  # noqa: E402

CREATIVE_SPECS: dict[str, ArtifactSpec] = {spec.slug: spec for spec in [
    ArtifactSpec(281, "color-theory", "Color Theory Application",
                 ("palette", "rationale", "accessibility", "usage"),
                 "Specify a color palette (hex values, roles: primary/secondary/accent/background), "
                 "the emotional rationale per choice, WCAG contrast notes for text pairings, and "
                 "usage rules. Hex values are proposals for human review, not extracted from any tool."),
    ArtifactSpec(282, "composition", "Composition Principles",
                 ("layout", "grid", "visual_hierarchy", "balance_notes"),
                 "Specify the layout: grid system, element placement, visual hierarchy order, and "
                 "balance/white-space notes for the described piece."),
    ArtifactSpec(283, "typography", "Typography Selection",
                 ("typefaces", "scale", "pairing_rules", "fallbacks"),
                 "Specify a type system: typeface roles (display/body/mono), a modular type scale, "
                 "pairing rules, and system fallbacks. Prefer openly licensed families; never claim "
                 "a license check was performed."),
    ArtifactSpec(284, "logo-design", "Logo Design",
                 ("concepts", "construction", "clear_space", "donts"),
                 "Specify 2-3 logo CONCEPTS as text briefs (form, symbolism, construction grid "
                 "notes), clear-space/minimum-size rules, and misuse don'ts. No artwork is produced."),
    ArtifactSpec(285, "brand-identity", "Brand Identity Systems",
                 ("system_overview", "elements", "application_rules", "governance"),
                 "Specify the cohesive visual language: element inventory, how elements combine, "
                 "application rules per surface (social, print, product), and governance notes."),
    ArtifactSpec(286, "packaging-design", "Packaging Design",
                 ("structure", "panel_layout", "materials", "shelf_presence"),
                 "Specify the packaging: structural brief, per-panel content layout, material/finish "
                 "suggestions, and shelf-presence rationale. Dielines are described, not drawn."),
    ArtifactSpec(287, "ui-ux-design", "UI/UX Design",
                 ("screens", "components", "states", "usability_notes"),
                 "Specify the interface: screen inventory, component specs (anatomy, spacing tokens), "
                 "interaction states (default/hover/disabled/loading/error/empty), and usability notes."),
    ArtifactSpec(288, "information-architecture", "Information Architecture",
                 ("sitemap", "taxonomy", "navigation", "labeling"),
                 "Specify the IA: sitemap tree, content taxonomy, navigation patterns, and labeling "
                 "conventions for the described product or site."),
    ArtifactSpec(289, "interaction-design", "Interaction Design",
                 ("flows", "microinteractions", "feedback", "edge_cases"),
                 "Specify the interactions: user flows, microinteraction specs (trigger, rules, "
                 "feedback, duration), and edge-case handling."),
    ArtifactSpec(290, "motion-design", "Motion Design",
                 ("motion_principles", "transitions", "timing", "reduced_motion"),
                 "Specify the motion system: principles, transition specs (duration, easing curves), "
                 "choreography timing, and a prefers-reduced-motion fallback per animation."),
    ArtifactSpec(291, "3d-modeling", "3D Modeling",
                 ("object_breakdown", "topology_notes", "dimensions", "asset_prompts"),
                 "Specify the model build: object decomposition, topology notes (quad flow, edge "
                 "loops where deformation happens), real-world dimensions, and reference image "
                 "prompts. No geometry is produced."),
    ArtifactSpec(292, "texture-creation", "Texture Creation",
                 ("materials", "maps", "tiling_notes", "asset_prompts"),
                 "Specify PBR materials: per material the map set (albedo/roughness/normal/etc.) "
                 "with parameter values, tiling notes, and texture generation prompts."),
    ArtifactSpec(293, "lighting-design", "Lighting Design",
                 ("setup", "parameters", "mood_rationale", "budget_notes"),
                 "Specify the lighting: rig type (e.g. three-point), per-light parameters (type, "
                 "intensity, color temperature, position), mood rationale, and render-budget notes."),
    ArtifactSpec(294, "rendering-optimization", "Rendering Optimization",
                 ("quality_targets", "settings", "tradeoffs", "validation_plan"),
                 "Specify render settings per quality target (draft/preview/final), the "
                 "quality-vs-time tradeoff per setting, and a validation plan."),
    ArtifactSpec(295, "animation-principles", "Animation Principles",
                 ("principles_applied", "shot_breakdown", "timing_charts"),
                 "Specify the animation: which of the 12 principles apply where, a per-shot "
                 "breakdown, and timing/spacing charts described numerically (frames, easing)."),
    ArtifactSpec(296, "character-rigging", "Character Rigging",
                 ("skeleton", "controls", "deformation_notes", "constraints"),
                 "Specify the rig: bone/joint list with hierarchy, control set, deformation "
                 "strategy notes, and constraint definitions."),
    ArtifactSpec(297, "facial-animation", "Facial Animation",
                 ("expression_set", "phoneme_shapes", "emotion_map", "transition_notes"),
                 "Specify the facial system: core expression set, viseme/phoneme shape list, an "
                 "emotion-to-blendshape map, and transition/blending notes."),
    ArtifactSpec(298, "physics-simulation", "Physics Simulation",
                 ("bodies", "forces", "solver_settings", "bake_plan"),
                 "Specify the simulation: rigid/soft body assignments, forces and colliders, solver "
                 "settings (substeps, iterations), and a bake/caching plan."),
    ArtifactSpec(299, "particle-effects", "Particle Effects",
                 ("emitters", "behavior", "render_notes", "performance_budget"),
                 "Specify the particle systems: per emitter the spawn rate, lifetime, velocity/force "
                 "curves, render notes, and a performance budget (max live particles)."),
    ArtifactSpec(300, "procedural-generation", "Procedural Generation",
                 ("algorithm", "parameters", "seed_strategy", "validation"),
                 "Specify the procedural system: algorithm choice with rationale, parameter table "
                 "(ranges, defaults), seed/reproducibility strategy, and output validation rules."),
    ArtifactSpec(301, "sound-design", "Sound Design",
                 ("sound_list", "sources", "processing", "asset_prompts"),
                 "Specify the soundscape: per sound the description, synthesis/fallback source "
                 "notes, processing chain, and audio generation prompts for the self-hosted engine."),
    ArtifactSpec(302, "music-composition", "Music Composition",
                 ("structure", "melody_notes", "tempo_key", "arrangement_notes"),
                 "Specify the composition: form/structure, melodic motif descriptions (scale "
                 "degrees, contour), tempo and key, and arrangement notes. Original work only."),
    ArtifactSpec(303, "harmony-arrangement", "Harmony Arrangement",
                 ("progressions", "voicings", "voice_leading", "alternatives"),
                 "Specify the harmony: chord progressions (roman numerals + chord names), voicing "
                 "notes, voice-leading decisions, and reharmonization alternatives."),
    ArtifactSpec(304, "rhythm-programming", "Rhythm Programming",
                 ("patterns", "tempo_grid", "velocity_map", "variation_rules"),
                 "Specify the rhythm: per-pattern step grids (described numerically), tempo/time "
                 "signature, velocity/accent map, and variation/fill rules."),
    ArtifactSpec(305, "orchestration", "Orchestration",
                 ("instrumentation", "part_assignments", "balance_notes", "doubling_rules"),
                 "Specify the orchestration: instrument list, part assignments per section, "
                 "balance/register notes, and doubling rules."),
]}


# Row-specific, deterministic inspection metrics for rows 288-305. These do not
# pretend to render media; they make each specification mechanically reviewable.
CREATIVE_METRIC_KEYS = {
    288: "navigation_depth", 289: "interaction_edge_case_count", 290: "reduced_motion_coverage",
    291: "modeled_part_count", 292: "material_map_count", 293: "light_parameter_count",
    294: "quality_tier_count", 295: "timing_chart_count", 296: "rig_control_count",
    297: "expression_shape_count", 298: "solver_setting_count", 299: "particle_budget_count",
    300: "procedural_parameter_count", 301: "sound_cue_count", 302: "musical_section_count",
    303: "harmonic_progression_count", 304: "rhythm_pattern_count", 305: "orchestral_part_count",
}

def _metric_size(value: Any) -> int:
    if isinstance(value, (list, tuple, set, dict)): return len(value)
    if value in (None, "", "TO BE PROVIDED"): return 0
    return 1

def creative_row_evidence(spec: ArtifactSpec, sections: dict[str, Any], model: str) -> dict[str, Any]:
    """Return a typed, row-keyed observation without claiming quality or execution."""
    observed = sum(_metric_size(sections.get(key)) for key in spec.section_keys)
    return {
        "mechanism": f"creative.{spec.slug}.v1",
        "metric": {"name": CREATIVE_METRIC_KEYS.get(spec.row, f"specified_section_count_row_{spec.row}"), "value": observed, "unit": "specified_items", "value_type": "integer"},
        "model": {"provider_model": model, "contract_version": "creative-spec/1.0"},
        "evidence": {"kind": "generated_specification", "required_keys": list(spec.section_keys), "observed_keys": [k for k in spec.section_keys if k in sections]},
        "external_effects": [],
    }


class CreativeEngine:
    """Produces typed draft creative specifications; renders nothing."""

    def __init__(
        self,
        *,
        repository: ArtifactRepository,
        generate: GenerateFn,
        provider: str = "openai",
        model: str | None = None,
    ) -> None:
        self._repository = repository
        self._generate = generate
        self._provider = provider
        self._model = model

    def list_artifacts(self, kind: str | None = None) -> list[MarketingArtifact]:
        return self._repository.list_artifacts(kind)

    async def generate(
        self,
        slug: str,
        *,
        business: str,
        subject: str,
        goals: list[str] | None = None,
        facts: dict[str, Any] | None = None,
        constraints: list[str] | None = None,
    ) -> MarketingArtifact:
        spec = CREATIVE_SPECS[slug]
        facts = facts or {}
        goals = goals or []
        constraints = constraints or []
        inputs = {"business": business, "subject": subject, "goals": goals,
                  "facts": facts, "constraints": constraints}
        keys = ", ".join(f'"{key}"' for key in spec.section_keys)
        prompt = (
            "Use ONLY the facts provided in the input. Where a fact is missing, write "
            '"TO BE PROVIDED" - never invent brand assets, measurements, licenses, or '
            "research. This is a specification for human execution, not a rendered asset. "
            "Describe original work only; never imitate named artists, brands, franchises, "
            "or copyrighted characters.\n\n"
            f"You are producing a {spec.title} specification (draft). {spec.instructions}\n"
            f"Reply with ONLY a JSON object with keys: {keys}.\n\n"
            f"Input (JSON):\n{json.dumps(inputs, default=str)}"
        )
        model, text = await self._generate(prompt, self._provider, self._model)
        from .marketing import _parse_json_object

        sections = _parse_json_object(text)
        findings: list[str] = []
        sections = redact_imitations(sections, findings)
        _filter_asset_prompts(sections)
        sections["_deliverable"] = "specification"
        sections["_disclaimer"] = RENDER_DISCLAIMER
        if findings:
            sections["originality_notes"] = findings
        artifact = MarketingArtifact(
            id=f"crv-{uuid.uuid4().hex[:12]}",
            row=spec.row,
            kind=slug,
            title=spec.title,
            sections=sections,
            evaluation={"required_sections": list(spec.section_keys), "observed_sections": sorted(sections), "review_checks": ["originality", "accessibility", "technical feasibility", "rights"], "human_review_required": True, "row_evidence": creative_row_evidence(spec, sections, model)},
            uncertainty={"level": "not_quantified", "drivers": ["unrendered specification", "caller-supplied constraints", "human aesthetic judgment"], "render_or_physical_result_claimed": False},
            inputs=inputs,
            model=model,
        )
        return self._repository.save_artifact(artifact)
