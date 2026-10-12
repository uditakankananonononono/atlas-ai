"""Source-traceable version bridge. Exact quotes prove presence, not entailment."""
from copy import deepcopy
from .lane_builder import DocumentBuilder
from .lane_grounding import GroundingEngine
from .schemas import CreateVersionRequest, Citation

def convert_outline(outline):
    doc = DocumentBuilder().build(outline)
    grounded = GroundingEngine().ground(doc)
    # Free prose has no claim evidence contract and must not be labelled grounded.
    if any(section.prose for section in doc.sections):
        raise ValueError('grounded versions require evidence-bearing claims; free prose is not grounded')
    if not any(section.claims for section in doc.sections):
        raise ValueError('grounded versions require at least one evidence-bearing claim')
    sections = [{'title':section.heading, 'body':'\n'.join(claim.text + ' ' + ''.join(f'[{n}]' for n in grounded.citation_numbers(si,ci)) for ci,claim in enumerate(section.claims))} for si,section in enumerate(doc.sections)]
    citations = [Citation(key=str(c.number),title=c.source.title,url=c.source.url,quote=c.quote) for c in grounded.citations]
    return doc.title, sections, citations

def grounded_request(outline, format, template_id):
    if format == 'pptx':
        raise ValueError('grounded version bridge supports PDF, LaTeX and DOCX; slide mapping is not implemented')
    title, sections, citations = convert_outline(outline)
    content = {'title':title, 'sections':sections, '_source_trace':deepcopy(outline),
               '_grounding_scope':'exact_quote_presence_only; semantic entailment and source authenticity unverified'}
    return CreateVersionRequest(title=title,format=format,template_id=template_id,content=content,citations=citations)

def validate_grounded_content(content, supplied_citations=None):
    outline = content.get('_source_trace')
    if outline is None:
        return {'status':'ungrounded', 'semantic_truth_verified':False}
    title, sections, citations = convert_outline(outline)
    if content.get('title') != title or content.get('sections') != sections:
        raise ValueError('grounded rendered content does not match its source-traceable outline')
    if supplied_citations is not None and [c.model_dump() for c in supplied_citations] != [c.model_dump() for c in citations]:
        raise ValueError('grounded version citations do not match its source trace')
    return {'status':'quote_presence_verified', 'semantic_truth_verified':False,
            'source_authenticity_verified':False,'citation_count':len(citations)}
