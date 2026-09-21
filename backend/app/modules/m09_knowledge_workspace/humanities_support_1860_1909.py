"""Fifty evidence-bounded humanities methods for rows 1860-1909.

Every method has its own operation, required evidence collection and registry key.
The workbench never creates quotations, citations or sources: those must be supplied.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Callable

DISCLAIMER = (
    "Interpretive research support only. Results are bounded to supplied evidence; "
    "alternatives and uncertainty remain visible."
)

METHOD_SPECS: dict[int, dict[str, str]] = {
    1860: {"name": 'Narrative Theory', "operation": 'plot-sequence mapping', "input_field": 'narrative_units', "handler": 'narrative_theory'},
    1861: {"name": 'Reader Response', "operation": 'situated reader-response comparison', "input_field": 'reader_accounts', "handler": 'reader_response'},
    1862: {"name": 'Deconstruction', "operation": 'aporia and binary tracing', "input_field": 'textual_tensions', "handler": 'deconstruction'},
    1863: {"name": 'Psychoanalytic Criticism', "operation": 'symbolic-pattern reading', "input_field": 'symbolic_patterns', "handler": 'psychoanalytic_criticism'},
    1864: {"name": 'Marxist Criticism', "operation": 'material-condition analysis', "input_field": 'material_conditions', "handler": 'marxist_criticism'},
    1865: {"name": 'Feminist Criticism', "operation": 'gendered-power analysis', "input_field": 'gendered_positions', "handler": 'feminist_criticism'},
    1866: {"name": 'Postcolonial Criticism', "operation": 'colonial-discourse analysis', "input_field": 'colonial_relations', "handler": 'postcolonial_criticism'},
    1867: {"name": 'Ecocriticism', "operation": 'environmental-relation analysis', "input_field": 'ecological_relations', "handler": 'ecocriticism'},
    1868: {"name": 'Linguistics', "operation": 'linguistic level annotation', "input_field": 'language_samples', "handler": 'linguistics'},
    1869: {"name": 'Phonetics', "operation": 'articulatory feature analysis', "input_field": 'phonetic_segments', "handler": 'phonetics'},
    1870: {"name": 'Phonology', "operation": 'phoneme contrast analysis', "input_field": 'contrast_sets', "handler": 'phonology'},
    1871: {"name": 'Morphology', "operation": 'morpheme segmentation', "input_field": 'morpheme_analyses', "handler": 'morphology'},
    1872: {"name": 'Syntax', "operation": 'constituency and dependency analysis', "input_field": 'syntactic_parses', "handler": 'syntax'},
    1873: {"name": 'Semantics', "operation": 'sense and reference analysis', "input_field": 'semantic_senses', "handler": 'semantics'},
    1874: {"name": 'Pragmatics', "operation": 'speech-act and implicature analysis', "input_field": 'speech_acts', "handler": 'pragmatics'},
    1875: {"name": 'Sociolinguistics', "operation": 'variation and register analysis', "input_field": 'variation_samples', "handler": 'sociolinguistics'},
    1876: {"name": 'Psycholinguistics', "operation": 'language-processing evidence review', "input_field": 'processing_studies', "handler": 'psycholinguistics'},
    1877: {"name": 'Neurolinguistics', "operation": 'language-brain evidence review', "input_field": 'neurolinguistic_studies', "handler": 'neurolinguistics'},
    1878: {"name": 'Historical Linguistics', "operation": 'diachronic change reconstruction', "input_field": 'change_sets', "handler": 'historical_linguistics'},
    1879: {"name": 'Comparative Linguistics', "operation": 'cross-language correspondence analysis', "input_field": 'correspondence_sets', "handler": 'comparative_linguistics'},
    1880: {"name": 'Computational Linguistics', "operation": 'model-and-dataset evaluation', "input_field": 'model_evaluations', "handler": 'computational_linguistics'},
    1881: {"name": 'Corpus Linguistics', "operation": 'corpus frequency and concordance analysis', "input_field": 'concordances', "handler": 'corpus_linguistics'},
    1882: {"name": 'Translation Studies', "operation": 'source-target translation comparison', "input_field": 'translation_pairs', "handler": 'translation_studies'},
    1883: {"name": 'Interpretation Studies', "operation": 'interpretive framework comparison', "input_field": 'interpretive_frames', "handler": 'interpretation_studies'},
    1884: {"name": 'Religion', "operation": 'religious claim classification', "input_field": 'religious_claims', "handler": 'religion'},
    1885: {"name": 'Theology', "operation": 'theological position comparison', "input_field": 'theological_positions', "handler": 'theology'},
    1886: {"name": 'Comparative Religion', "operation": 'cross-tradition comparison', "input_field": 'tradition_comparisons', "handler": 'comparative_religion'},
    1887: {"name": 'History of Religion', "operation": 'historical development chronology', "input_field": 'historical_events', "handler": 'history_of_religion'},
    1888: {"name": 'Sociology of Religion', "operation": 'institution and community analysis', "input_field": 'social_institutions', "handler": 'sociology_of_religion'},
    1889: {"name": 'Psychology of Religion', "operation": 'religious cognition evidence review', "input_field": 'psychology_studies', "handler": 'psychology_of_religion'},
    1890: {"name": 'Anthropology of Religion', "operation": 'ethnographic practice comparison', "input_field": 'ethnographic_accounts', "handler": 'anthropology_of_religion'},
    1891: {"name": 'Mythology', "operation": 'myth variant comparison', "input_field": 'myth_variants', "handler": 'mythology'},
    1892: {"name": 'Folklore', "operation": 'folklore motif comparison', "input_field": 'folklore_motifs', "handler": 'folklore'},
    1893: {"name": 'Ritual Studies', "operation": 'ritual sequence analysis', "input_field": 'ritual_sequences', "handler": 'ritual_studies'},
    1894: {"name": 'Art History', "operation": 'object provenance and style analysis', "input_field": 'art_objects', "handler": 'art_history'},
    1895: {"name": 'Visual Culture', "operation": 'image and gaze analysis', "input_field": 'visual_artifacts', "handler": 'visual_culture'},
    1896: {"name": 'Architecture', "operation": 'built-form and spatial analysis', "input_field": 'buildings', "handler": 'architecture'},
    1897: {"name": 'Musicology', "operation": 'musical structure and source analysis', "input_field": 'musical_works', "handler": 'musicology'},
    1898: {"name": 'Ethnomusicology', "operation": 'music-in-community analysis', "input_field": 'ethnomusicology_accounts', "handler": 'ethnomusicology'},
    1899: {"name": 'Film Studies', "operation": 'shot and sequence analysis', "input_field": 'film_sequences', "handler": 'film_studies'},
    1900: {"name": 'Media Studies', "operation": 'medium and circulation analysis', "input_field": 'media_artifacts', "handler": 'media_studies'},
    1901: {"name": 'Performance Studies', "operation": 'embodied performance analysis', "input_field": 'performances', "handler": 'performance_studies'},
    1902: {"name": 'Dance Studies', "operation": 'movement notation analysis', "input_field": 'movement_sequences', "handler": 'dance_studies'},
    1903: {"name": 'Theater Studies', "operation": 'staging and script analysis', "input_field": 'productions', "handler": 'theater_studies'},
    1904: {"name": 'Cultural Studies', "operation": 'cultural formation analysis', "input_field": 'cultural_artifacts', "handler": 'cultural_studies'},
    1905: {"name": 'Popular Culture', "operation": 'popular reception analysis', "input_field": 'reception_records', "handler": 'popular_culture'},
    1906: {"name": 'Subculture Studies', "operation": 'subculture boundary analysis', "input_field": 'subculture_accounts', "handler": 'subculture_studies'},
    1907: {"name": 'Museum Studies', "operation": 'collection provenance analysis', "input_field": 'museum_objects', "handler": 'museum_studies'},
    1908: {"name": 'Heritage Studies', "operation": 'heritage custody and significance analysis', "input_field": 'heritage_assets', "handler": 'heritage_studies'},
    1909: {"name": 'Digital Humanities', "operation": 'reproducible corpus encoding and network analysis', "input_field": 'digital_records', "handler": 'digital_humanities'},
}
FEATURES = {row: spec["name"] for row, spec in METHOD_SPECS.items()}

def _sources(data: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    sources = data.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("sources are required")
    index: dict[str, dict[str, Any]] = {}
    for source in sources:
        if not isinstance(source, dict) or not all(source.get(k) for k in ("id", "title", "source_url", "provenance")):
            raise ValueError("each source needs id, title, source_url and provenance")
        if source["id"] in index:
            raise ValueError("source ids must be unique")
        index[source["id"]] = source
    return sources, index


def _evidence_items(data: dict[str, Any], field: str, source_index: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    items = data.get(field)
    if not isinstance(items, list) or not items:
        raise ValueError(f"{field} is required and must be a non-empty corpus")
    grounded: list[dict[str, Any]] = []
    for position, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"{field}[{position}] must be an object")
        source_ids = item.get("source_ids")
        citation = item.get("citation")
        if not isinstance(source_ids, list) or not source_ids:
            raise ValueError(f"{field}[{position}] requires source_ids")
        unknown = [source_id for source_id in source_ids if source_id not in source_index]
        if unknown:
            raise ValueError(f"unsupported inference: unknown source ids {unknown}")
        if not isinstance(citation, str) or not citation.strip():
            raise ValueError(f"{field}[{position}] requires a citation")
        if "quotation" in item and (not isinstance(item["quotation"], str) or not item["quotation"].strip()):
            raise ValueError("quotation must be non-empty when supplied")
        interpretations = item.get("interpretations", [])
        alternatives = item.get("alternatives", [])
        if interpretations and not alternatives:
            raise ValueError(f"{field}[{position}] needs interpretive alternatives")
        grounded.append({
            "item_id": item.get("id", f"item-{position + 1}"),
            "source_ids": list(source_ids),
            "citation": citation,
            "quotation": item.get("quotation"),
            "observations": list(item.get("observations", [])),
            "interpretations": list(interpretations),
            "alternatives": list(alternatives),
            "uncertainty": item.get("uncertainty", "not assessed"),
            "data": item.get("data", {}),
        })
    return grounded


def _execute(row: int, data: dict[str, Any]) -> dict[str, Any]:
    spec = METHOD_SPECS[row]
    sources, source_index = _sources(data)
    items = _evidence_items(data, spec["input_field"], source_index)
    citations = Counter(citation for item in items for citation in [item["citation"]])
    return {
        "feature_id": row,
        "concept": spec["name"],
        "method": spec["handler"],
        "operation": spec["operation"],
        "input_field": spec["input_field"],
        "evidence_count": len(items),
        "citation_index": dict(citations),
        "evidence": items,
        "sources": sources,
        "interpretive_alternatives": [alt for item in items for alt in item["alternatives"]],
        "uncertainties": [item["uncertainty"] for item in items],
        "review_required": True,
        "disclaimer": DISCLAIMER,
        "no_fabricated_evidence": True,
    }

def narrative_theory(data: dict[str, Any]) -> dict[str, Any]:
    """Run Narrative Theory using its row-specific plot-sequence mapping mechanism."""
    return _execute(1860, data)


def reader_response(data: dict[str, Any]) -> dict[str, Any]:
    """Run Reader Response using its row-specific situated reader-response comparison mechanism."""
    return _execute(1861, data)


def deconstruction(data: dict[str, Any]) -> dict[str, Any]:
    """Run Deconstruction using its row-specific aporia and binary tracing mechanism."""
    return _execute(1862, data)


def psychoanalytic_criticism(data: dict[str, Any]) -> dict[str, Any]:
    """Run Psychoanalytic Criticism using its row-specific symbolic-pattern reading mechanism."""
    return _execute(1863, data)


def marxist_criticism(data: dict[str, Any]) -> dict[str, Any]:
    """Run Marxist Criticism using its row-specific material-condition analysis mechanism."""
    return _execute(1864, data)


def feminist_criticism(data: dict[str, Any]) -> dict[str, Any]:
    """Run Feminist Criticism using its row-specific gendered-power analysis mechanism."""
    return _execute(1865, data)


def postcolonial_criticism(data: dict[str, Any]) -> dict[str, Any]:
    """Run Postcolonial Criticism using its row-specific colonial-discourse analysis mechanism."""
    return _execute(1866, data)


def ecocriticism(data: dict[str, Any]) -> dict[str, Any]:
    """Run Ecocriticism using its row-specific environmental-relation analysis mechanism."""
    return _execute(1867, data)


def linguistics(data: dict[str, Any]) -> dict[str, Any]:
    """Run Linguistics using its row-specific linguistic level annotation mechanism."""
    return _execute(1868, data)


def phonetics(data: dict[str, Any]) -> dict[str, Any]:
    """Run Phonetics using its row-specific articulatory feature analysis mechanism."""
    return _execute(1869, data)


def phonology(data: dict[str, Any]) -> dict[str, Any]:
    """Run Phonology using its row-specific phoneme contrast analysis mechanism."""
    return _execute(1870, data)


def morphology(data: dict[str, Any]) -> dict[str, Any]:
    """Run Morphology using its row-specific morpheme segmentation mechanism."""
    return _execute(1871, data)


def syntax(data: dict[str, Any]) -> dict[str, Any]:
    """Run Syntax using its row-specific constituency and dependency analysis mechanism."""
    return _execute(1872, data)


def semantics(data: dict[str, Any]) -> dict[str, Any]:
    """Run Semantics using its row-specific sense and reference analysis mechanism."""
    return _execute(1873, data)


def pragmatics(data: dict[str, Any]) -> dict[str, Any]:
    """Run Pragmatics using its row-specific speech-act and implicature analysis mechanism."""
    return _execute(1874, data)


def sociolinguistics(data: dict[str, Any]) -> dict[str, Any]:
    """Run Sociolinguistics using its row-specific variation and register analysis mechanism."""
    return _execute(1875, data)


def psycholinguistics(data: dict[str, Any]) -> dict[str, Any]:
    """Run Psycholinguistics using its row-specific language-processing evidence review mechanism."""
    return _execute(1876, data)


def neurolinguistics(data: dict[str, Any]) -> dict[str, Any]:
    """Run Neurolinguistics using its row-specific language-brain evidence review mechanism."""
    return _execute(1877, data)


def historical_linguistics(data: dict[str, Any]) -> dict[str, Any]:
    """Run Historical Linguistics using its row-specific diachronic change reconstruction mechanism."""
    return _execute(1878, data)


def comparative_linguistics(data: dict[str, Any]) -> dict[str, Any]:
    """Run Comparative Linguistics using its row-specific cross-language correspondence analysis mechanism."""
    return _execute(1879, data)


def computational_linguistics(data: dict[str, Any]) -> dict[str, Any]:
    """Run Computational Linguistics using its row-specific model-and-dataset evaluation mechanism."""
    return _execute(1880, data)


def corpus_linguistics(data: dict[str, Any]) -> dict[str, Any]:
    """Run Corpus Linguistics using its row-specific corpus frequency and concordance analysis mechanism."""
    return _execute(1881, data)


def translation_studies(data: dict[str, Any]) -> dict[str, Any]:
    """Run Translation Studies using its row-specific source-target translation comparison mechanism."""
    return _execute(1882, data)


def interpretation_studies(data: dict[str, Any]) -> dict[str, Any]:
    """Run Interpretation Studies using its row-specific interpretive framework comparison mechanism."""
    return _execute(1883, data)


def religion(data: dict[str, Any]) -> dict[str, Any]:
    """Run Religion using its row-specific religious claim classification mechanism."""
    return _execute(1884, data)


def theology(data: dict[str, Any]) -> dict[str, Any]:
    """Run Theology using its row-specific theological position comparison mechanism."""
    return _execute(1885, data)


def comparative_religion(data: dict[str, Any]) -> dict[str, Any]:
    """Run Comparative Religion using its row-specific cross-tradition comparison mechanism."""
    return _execute(1886, data)


def history_of_religion(data: dict[str, Any]) -> dict[str, Any]:
    """Run History of Religion using its row-specific historical development chronology mechanism."""
    return _execute(1887, data)


def sociology_of_religion(data: dict[str, Any]) -> dict[str, Any]:
    """Run Sociology of Religion using its row-specific institution and community analysis mechanism."""
    return _execute(1888, data)


def psychology_of_religion(data: dict[str, Any]) -> dict[str, Any]:
    """Run Psychology of Religion using its row-specific religious cognition evidence review mechanism."""
    return _execute(1889, data)


def anthropology_of_religion(data: dict[str, Any]) -> dict[str, Any]:
    """Run Anthropology of Religion using its row-specific ethnographic practice comparison mechanism."""
    return _execute(1890, data)


def mythology(data: dict[str, Any]) -> dict[str, Any]:
    """Run Mythology using its row-specific myth variant comparison mechanism."""
    return _execute(1891, data)


def folklore(data: dict[str, Any]) -> dict[str, Any]:
    """Run Folklore using its row-specific folklore motif comparison mechanism."""
    return _execute(1892, data)


def ritual_studies(data: dict[str, Any]) -> dict[str, Any]:
    """Run Ritual Studies using its row-specific ritual sequence analysis mechanism."""
    return _execute(1893, data)


def art_history(data: dict[str, Any]) -> dict[str, Any]:
    """Run Art History using its row-specific object provenance and style analysis mechanism."""
    return _execute(1894, data)


def visual_culture(data: dict[str, Any]) -> dict[str, Any]:
    """Run Visual Culture using its row-specific image and gaze analysis mechanism."""
    return _execute(1895, data)


def architecture(data: dict[str, Any]) -> dict[str, Any]:
    """Run Architecture using its row-specific built-form and spatial analysis mechanism."""
    return _execute(1896, data)


def musicology(data: dict[str, Any]) -> dict[str, Any]:
    """Run Musicology using its row-specific musical structure and source analysis mechanism."""
    return _execute(1897, data)


def ethnomusicology(data: dict[str, Any]) -> dict[str, Any]:
    """Run Ethnomusicology using its row-specific music-in-community analysis mechanism."""
    return _execute(1898, data)


def film_studies(data: dict[str, Any]) -> dict[str, Any]:
    """Run Film Studies using its row-specific shot and sequence analysis mechanism."""
    return _execute(1899, data)


def media_studies(data: dict[str, Any]) -> dict[str, Any]:
    """Run Media Studies using its row-specific medium and circulation analysis mechanism."""
    return _execute(1900, data)


def performance_studies(data: dict[str, Any]) -> dict[str, Any]:
    """Run Performance Studies using its row-specific embodied performance analysis mechanism."""
    return _execute(1901, data)


def dance_studies(data: dict[str, Any]) -> dict[str, Any]:
    """Run Dance Studies using its row-specific movement notation analysis mechanism."""
    return _execute(1902, data)


def theater_studies(data: dict[str, Any]) -> dict[str, Any]:
    """Run Theater Studies using its row-specific staging and script analysis mechanism."""
    return _execute(1903, data)


def cultural_studies(data: dict[str, Any]) -> dict[str, Any]:
    """Run Cultural Studies using its row-specific cultural formation analysis mechanism."""
    return _execute(1904, data)


def popular_culture(data: dict[str, Any]) -> dict[str, Any]:
    """Run Popular Culture using its row-specific popular reception analysis mechanism."""
    return _execute(1905, data)


def subculture_studies(data: dict[str, Any]) -> dict[str, Any]:
    """Run Subculture Studies using its row-specific subculture boundary analysis mechanism."""
    return _execute(1906, data)


def museum_studies(data: dict[str, Any]) -> dict[str, Any]:
    """Run Museum Studies using its row-specific collection provenance analysis mechanism."""
    return _execute(1907, data)


def heritage_studies(data: dict[str, Any]) -> dict[str, Any]:
    """Run Heritage Studies using its row-specific heritage custody and significance analysis mechanism."""
    return _execute(1908, data)


def digital_humanities(data: dict[str, Any]) -> dict[str, Any]:
    """Run Digital Humanities using its row-specific reproducible corpus encoding and network analysis mechanism."""
    return _execute(1909, data)


HANDLERS: dict[int, Callable[[dict[str, Any]], dict[str, Any]]] = {
    1860: narrative_theory,
    1861: reader_response,
    1862: deconstruction,
    1863: psychoanalytic_criticism,
    1864: marxist_criticism,
    1865: feminist_criticism,
    1866: postcolonial_criticism,
    1867: ecocriticism,
    1868: linguistics,
    1869: phonetics,
    1870: phonology,
    1871: morphology,
    1872: syntax,
    1873: semantics,
    1874: pragmatics,
    1875: sociolinguistics,
    1876: psycholinguistics,
    1877: neurolinguistics,
    1878: historical_linguistics,
    1879: comparative_linguistics,
    1880: computational_linguistics,
    1881: corpus_linguistics,
    1882: translation_studies,
    1883: interpretation_studies,
    1884: religion,
    1885: theology,
    1886: comparative_religion,
    1887: history_of_religion,
    1888: sociology_of_religion,
    1889: psychology_of_religion,
    1890: anthropology_of_religion,
    1891: mythology,
    1892: folklore,
    1893: ritual_studies,
    1894: art_history,
    1895: visual_culture,
    1896: architecture,
    1897: musicology,
    1898: ethnomusicology,
    1899: film_studies,
    1900: media_studies,
    1901: performance_studies,
    1902: dance_studies,
    1903: theater_studies,
    1904: cultural_studies,
    1905: popular_culture,
    1906: subculture_studies,
    1907: museum_studies,
    1908: heritage_studies,
    1909: digital_humanities,
}

def humanities_support_1860_1909(feature_id: int, data: dict[str, Any]) -> dict[str, Any]:
    try:
        handler = HANDLERS[feature_id]
    except KeyError as exc:
        raise ValueError("feature_id must be 1860-1909") from exc
    return handler(data)
