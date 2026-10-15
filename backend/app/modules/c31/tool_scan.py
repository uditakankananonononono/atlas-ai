"""S1.1 / c31.tool_scan - tool-landscape scanner.

Source excerpt (verbatim): "Has a whole troop of agents inspired but better
than Cellcog, strawberry browser and similar tools maybe search up yc
companies and replicate them and integrate into atlas".

Capability matrix + gap list over SUPPLIED tool records (YC directory exports,
repo pages, product pages saved as text). No live crawling. Stdlib only,
offline, deterministic.
"""
from __future__ import annotations

from app.modules.c30 import policy

PREFIX = "FLEET"
MAX_TOOLS = 4096
LICENSES = ("mit", "apache", "bsd", "gpl", "proprietary", "unknown")
PRICE_TIERS = ("free", "freemium", "paid")


def scan(tools, atlas_modules=None, purchase=False):
    """Build a capability matrix from supplied tool records + gap list."""
    if purchase:
        policy.check("spend", PREFIX)  # paid tools are per-action approval
    if isinstance(tools, bool) or not isinstance(tools, (list, tuple)):
        raise ValueError("FLEET_REFUSED_NOSOURCE")
    if not tools:
        raise ValueError("FLEET_REFUSED_NOSOURCE")
    if len(tools) > MAX_TOOLS:
        raise ValueError("FLEET_REFUSED_OVERSIZE")
    matrix = []
    seen = set()
    for t in tools:
        if not isinstance(t, dict):
            raise ValueError("FLEET_REFUSED_BAD_TYPE:tool")
        name = policy.clean_text(t.get("name"), PREFIX, "name", 128)
        if name in seen:
            raise ValueError("FLEET_REFUSED_DUPLICATE:" + name)
        seen.add(name)
        license_ = t.get("license", "unknown")
        if license_ not in LICENSES:
            raise ValueError("FLEET_REFUSED_BAD_LICENSE:" + str(license_)[:64])
        tier = t.get("price_tier", "unknown")
        if tier not in PRICE_TIERS + ("unknown",):
            raise ValueError("FLEET_REFUSED_BAD_PRICE_TIER:" + str(tier)[:64])
        caps = t.get("capabilities", [])
        if not isinstance(caps, (list, tuple)):
            raise ValueError("FLEET_REFUSED_BAD_TYPE:capabilities")
        caps = sorted({policy.clean_text(c, PREFIX, "capability", 128) for c in caps})
        matrix.append({"name": name, "license": license_, "price_tier": tier,
                       "capabilities": caps})
    matrix.sort(key=lambda r: r["name"])
    covered = set()
    for r in matrix:
        covered.update(r["capabilities"])
    own = set()
    if atlas_modules is not None:
        if not isinstance(atlas_modules, (list, tuple)):
            raise ValueError("FLEET_REFUSED_BAD_TYPE:atlas_modules")
        own = {policy.clean_text(m, PREFIX, "atlas_module", 128) for m in atlas_modules}
    gaps = sorted(covered - own)
    return {"matrix": matrix, "tool_count": len(matrix),
            "capability_count": len(covered), "gap_list": gaps, "gap_count": len(gaps),
            "scope": policy.scope(
                ["capability matrix over supplied records", "computed gap list"],
                ["live crawling", "installing or buying any tool"],
                "supplied tool records")}


def report(tools, atlas_modules=None):
    return scan(tools, atlas_modules)


def scan_sources(request):
    """Extract explicitly labelled fields from saved source text.

    A page's license/price claims are evidence, not verified permissions. This
    parser does not infer capabilities or license from unlabelled advertising.
    CSV/YC vendor-specific schemas are not assumed or silently guessed.
    """
    import re
    from urllib.parse import urlsplit
    if type(request) is not dict or set(request)!={'sources','atlas_modules'}:
        raise ValueError('FLEET_REFUSED_FIELDS')
    if type(request['sources']) is not list or not 1<=len(request['sources'])<=MAX_TOOLS:
        raise ValueError('FLEET_REFUSED_NOSOURCE')
    records=[];sources=[];seen=set()
    for row in request['sources']:
        if type(row) is not dict or set(row)!={'id','name','url','text'}:raise ValueError('FLEET_REFUSED_SOURCE')
        ident=policy.clean_text(row['id'],PREFIX,'source_id',128)
        if ident in seen:raise ValueError('FLEET_REFUSED_DUPLICATE_SOURCE')
        seen.add(ident)
        name=policy.clean_text(row['name'],PREFIX,'name',128)
        url=policy.clean_text(row['url'],PREFIX,'url',2048)
        parsed=urlsplit(url)
        if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password:raise ValueError('FLEET_REFUSED_SOURCE_URL')
        body=policy.clean_text(row['text'],PREFIX,'source_text',200000,allow_ws=True)
        fields={'license':set(),'price_tier':set()};caps=set();evidence=[]
        for match in re.finditer(r'^(License|Pricing|Price tier|Capabilities|Capability):[ \t]*([^\r\n]+)',body,flags=re.IGNORECASE|re.MULTILINE|re.ASCII):
            label=match.group(1).lower();value=match.group(2).strip()
            if label=='license':field='license'
            elif label in ('pricing','price tier'):field='price_tier'
            elif label in ('capabilities','capability'):field='capabilities'
            else:continue
            if field=='capabilities':
                values=[policy.clean_text(v.strip(),PREFIX,'capability',128) for v in value.split(',')]
                caps.update(values)
            else:
                normalized=value.casefold()
                allowed=LICENSES if field=='license' else PRICE_TIERS+('unknown',)
                if normalized not in allowed:normalized='unknown'
                fields[field].add(normalized)
            evidence.append({'field':field,'quote':match.group(),'start':match.start(),'end':match.end()})
        if any(len(values)>1 for values in fields.values()):raise ValueError('FLEET_REFUSED_AMBIGUOUS_SOURCE_FIELDS')
        records.append({'name':name,'license':next(iter(fields['license']),'unknown'),
                        'price_tier':next(iter(fields['price_tier']),'unknown'),'capabilities':sorted(caps)})
        sources.append({'source_id':ident,'name':name,'url':url,'evidence':evidence,
                        'missing_fields':[k for k,v in fields.items() if not v]+([] if caps else ['capabilities'])})
    out=scan(records,request['atlas_modules'])
    out.update(source_records=sources,sources_verified=False,
               extraction_method='explicit labelled source lines only; unlabelled text ignored')
    out['scope']['not_implemented']+=['license or price verification','arbitrary page semantic extraction','vendor-specific raw CSV import']
    return out
