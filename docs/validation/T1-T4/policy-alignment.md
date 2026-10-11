# Canonical policy alignment

Supersedes previous shared_policy import and old candidate guard pins. Verified public main c05fa97c contains backend/app/modules/c30/policy.py, imported as app.modules.c30.policy. shared_policy calls check(action, prefix), not the absent guard function. Prefix mapping: T1 APPLY; T2/T3 TREND; T4 FLEET. Flat action dict selects a flagged deny rule or type, default analyze. check() is DENY-ONLY: unknown including analyze refuses; the default engine cannot produce a report even for an otherwise safe offline run until integration selects a permitted canonical descriptor path. No allow behavior fabricated. Injected server-only hook remains test/deployment configuration and is not client-controlled.

Gate Python3.12.14 pytest8.4.2 with actual conftest: 55 passed, one deprecation warning. Canonical check stub records (spend, prefix) and raises exact unit-family refusal on every T unit; missing canonical module pinned APPLY_REFUSED_UNAVAILABLE. ValueError remains HTTP422. Stub tests prove adapter use, not full canonical descriptor integration.

Fresh complete campaign on changed source: 480 generated/executed, 427 killed, 53 survivors. No all-killed claim. This replaces 471/425/46 counts for current source. Every survivor below is disclosed. String-code survivors remain exact full-code pin gaps; substring refusal assertions are narrower. Docstrings and redundant checks may be equivalent; these are not silently deducted. See JSON for exact source and mutant ids.

- #0 L1 string +X: `"""T1-T4 bounded ingestion and advice preparation. No sending or training runtime."""`
- #19 L48 delete call: `        public_url(url);public_url(self.origin);public_url(self.terms_url)`
- #24 L60 string +X: `    """Caller supplies a bounded, no-redirect transport. No credentials accepted.`
- #26 L69 delete call: `        public_url(url)`
- #135 L21 string +X: `        raise Refusal('TREND_REFUSED_SCRAPE')`
- #137 L26 string +X: `        raise Refusal('TREND_REFUSED_SCRAPE')`
- #140 L29 string +X: `        raise Refusal('TREND_REFUSED_SCRAPE')`
- #142 L31 string +X: `        raise Refusal('TREND_REFUSED_SCRAPE')`
- #149 L80 integer +1: `        delay=rp.crawl_delay('AtlasPublicCorpus') or rp.crawl_delay('*') or 0`
- #153 L112 string +X: `    action=next((name for name in ('spend','outreach','fakeacct','autopost','scrape','trade') if payload.get(name)),payload.get('type','analyze'))`
- #154 L112 string +X: `    action=next((name for name in ('spend','outreach','fakeacct','autopost','scrape','trade') if payload.get(name)),payload.get('type','analyze'))`
- #188 L177 string +X: `        self._records({'records':[{'source_id':p.get('source_id'),'url':p.get('url'),'text':content,'as_of':p.get('as_of'), **{flag:p.get(flag) for flag in ('paywalled','piracy','c`
- #206 L24 string +X: `    except ValueError: raise Refusal('TREND_REFUSED_SCRAPE')`
- #213 L34 string +X: `        if not ip.is_global: raise Refusal('TREND_REFUSED_SCRAPE')`
- #215 L50 string +X: `            raise Refusal('TREND_REFUSED_SCRAPE')`
- #216 L51 string +X: `        if urlsplit(url).netloc.lower()!=urlsplit(self.origin).netloc.lower():raise Refusal('TREND_REFUSED_SCRAPE')`
- #218 L66 string +X: `        if interval<60 or not 1<=limit<=100000:raise Refusal('TREND_REFUSED_LIMIT')`
- #219 L71 string +X: `        if permit is None:raise Refusal('TREND_REFUSED_SCRAPE')`
- #220 L74 string +X: `        if now-self.last.get(host,float('-inf'))<self.interval:raise Refusal('TREND_REFUSED_RATELIMIT')`
- #223 L77 string +X: `        if robots.status!=200 or len(robots.text.encode())>self.limit:raise Refusal('TREND_REFUSED_SCRAPE')`
- #224 L79 string +X: `        if not rp.can_fetch('AtlasPublicCorpus',url):raise Refusal('TREND_REFUSED_SCRAPE')`
- #225 L79 string +X: `        if not rp.can_fetch('AtlasPublicCorpus',url):raise Refusal('TREND_REFUSED_SCRAPE')`
- #226 L80 string +X: `        delay=rp.crawl_delay('AtlasPublicCorpus') or rp.crawl_delay('*') or 0`
- #227 L80 string +X: `        delay=rp.crawl_delay('AtlasPublicCorpus') or rp.crawl_delay('*') or 0`
- #228 L81 string +X: `        if delay>self.interval:raise Refusal('TREND_REFUSED_RATELIMIT')`
- #229 L83 string +X: `        if reply.status!=200:raise Refusal('TREND_REFUSED_FETCH')`
- #230 L84 string +X: `        if len(reply.text.encode())>self.limit:raise Refusal('TREND_REFUSED_OVERSIZE')`
- #254 L148 string +X: `        if unit not in ('T1','T2','T3','T4') or not isinstance(payload,dict):raise Refusal('TREND_REFUSED_SCHEMA')`
- #273 L176 string +X: `        if kind not in ('blog','podcast','git') or not isinstance(content,str):raise Refusal('TREND_REFUSED_SCHEMA')`
- #277 L180 string +X: `        if not isinstance(query,str) or len(query)>1000:raise Refusal('TREND_REFUSED_SCHEMA')`
- #300 L76 string +X: `        robots=self.transport(permit.origin.rstrip('/')+'/robots.txt',self.limit)`
- #301 L92 integer +1: `        if tag in ('script','style'):self.hidden=max(0,self.hidden-1)`
- #305 L110 string +X: `    except ImportError as exc:raise Refusal(prefix+'_REFUSED_UNAVAILABLE') from exc`
- #307 L112 string +X: `    action=next((name for name in ('spend','outreach','fakeacct','autopost','scrape','trade') if payload.get(name)),payload.get('type','analyze'))`
- #308 L112 string +X: `    action=next((name for name in ('spend','outreach','fakeacct','autopost','scrape','trade') if payload.get(name)),payload.get('type','analyze'))`
- #309 L112 string +X: `    action=next((name for name in ('spend','outreach','fakeacct','autopost','scrape','trade') if payload.get(name)),payload.get('type','analyze'))`
- #310 L112 string +X: `    action=next((name for name in ('spend','outreach','fakeacct','autopost','scrape','trade') if payload.get(name)),payload.get('type','analyze'))`
- #311 L112 string +X: `    action=next((name for name in ('spend','outreach','fakeacct','autopost','scrape','trade') if payload.get(name)),payload.get('type','analyze'))`
- #313 L120 string +X: `            raise Refusal(prefix+'_REFUSED_ACTION_SHAPE')`
- #316 L124 string +X: `            raise Refusal(prefix+'_REFUSED_ACTION')`
- #317 L127 string +X: `        if not isinstance(records,list) or len(records)>500:raise Refusal(prefix+'_REFUSED_OVERSIZE')`
- #318 L132 string +X: `            if r.get('piracy'):raise Refusal('TREND_REFUSED_PIRACY')`
- #335 L154 string +X: `            if not records:raise Refusal('FLEET_REFUSED_NOADVICE')`
- #365 L200 string +X: `            raise Refusal('TREND_REFUSED_PARSE') from exc`
- #377 L130 string +X: `            if not isinstance(r,dict):raise Refusal(prefix+'_REFUSED_SCHEMA')`
- #378 L131 string +X: `            if r.get('paywalled'):raise Refusal(prefix+'_REFUSED_PAYWALL')`
- #379 L133 string +X: `            if r.get('credentials') or r.get('logged_in'):raise Refusal(prefix+'_REFUSED_SCRAPE')`
- #380 L135 string +X: `            if permit is None:raise Refusal(prefix+'_REFUSED_SCRAPE')`
- #382 L139 string +X: `            if not isinstance(text,str) or len(text.encode())>100000:raise Refusal(prefix+'_REFUSED_OVERSIZE')`
- #384 L140 string +X: `            if not isinstance(r.get('as_of'),str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',r['as_of']):raise Refusal(prefix+'_REFUSED_DATE')`
- #399 L186 string +X: `                if '<!DOCTYPE' in content.upper() or '<!ENTITY' in content.upper():raise Refusal('TREND_REFUSED_XML')`
- #413 L137 string +X: `            except Refusal as exc:raise Refusal(prefix+'_REFUSED_SCRAPE') from exc`
- #477 L208 string +X: `            if all(term in (str(r['title'])+' '+str(r['summary'])).lower() for term in query.lower().split()):accepted.append(r)`

Earlier repair-audit.md analysis remains useful for unchanged sites, but its line numbers/counts refer to the pre-alignment file. Remaining runtime limits: regex-only source dates; no transport DNS resolution; malformed HTML balancing; robotparser agent substring semantics; no grants on candidates, no live training/global action hook/durable store/S9 verdict. No task completion claim.
