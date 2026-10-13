"""Frontier invention layer ported from a ChatGPT-generated bundle (pure logic only).

Not mounted, no module status changed. The bundle's own SQLite runtime, OAuth, API and
provider connectors were NOT ported: they duplicate Atlas auth, durable execution and
the guardrail egress gate. Any outbound effect must go through
GuardrailEnforcer.dispatch_outbound.
"""
from .closure import GapClosureEngine, CompletionRejected
from .compiler import CapabilityCompiler
from .evidence import EvidenceLattice
from .research_router import ResearchRouter, MechanismBridgeFinder, CounterexampleForge
from .skill_ecology import SkillEcology, SkillRejected
from .preference_model import PreferenceCodec, InMemoryPreferenceStore, PreferenceStore
from .data_gate import TrainingDataGate
from .representation_inventor import RepresentationInventor, TabularObservation
from .novelty_debt import NoveltyDebtLedger
from .cycle import FrontierCycle
from .evaluator_inventor import EvaluationDimensionInventor
