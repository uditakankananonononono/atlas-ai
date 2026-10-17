// Parser for the exact M06 publish review an approval request carries (payload.publish_snapshot, version 2).
// Mirrors the backend contract (publish_targets.valid_target / review_binding.publish_snapshot). Fails closed:
// anything that is not a complete version 2 snapshot agreeing with the request's own payload is reported as a
// problem, and the review panel then refuses to offer Approve. No account name or handle is ever inferred.
export const SOCIAL_MODULE_ID=6;
export const SOCIAL_PUBLISH_ACTIONS=["schedule_post"];
export type PublishSnapshot={platform:string;accountId:string;format:string|null;text:string;publishAt:string;mediaUrls:string[];altTexts:string[];threadChunks:string[];link:string|null;sponsored:boolean};
export type SnapshotResult={ok:true;snapshot:PublishSnapshot}|{ok:false;problems:string[]};
const PLATFORMS=["instagram","linkedin","twitter","tiktok"];
const isObj=(v:unknown):v is Record<string,unknown>=>typeof v==="object"&&v!==null&&!Array.isArray(v);
const nonEmpty=(v:unknown):v is string=>typeof v==="string"&&v.trim().length>0;
const strList=(v:unknown):string[]|null=>Array.isArray(v)&&v.every(x=>typeof x==="string")?v as string[]:null;
const sameInstant=(a:string,b:string)=>{const x=Date.parse(a),y=Date.parse(b);return Number.isFinite(x)&&Number.isFinite(y)&&x===y};
const hasZone=(s:string)=>/(Z|[+-]\d{2}:?\d{2})$/i.test(s.trim());
export function validAccountId(platform:string,id:unknown):boolean{
  if(typeof id!=="string"||!id||id.length>256)return false;
  return (platform==="tiktok"?/^[A-Za-z0-9_.:-]+$/:/^[0-9]+$/).test(id);
}
export function parsePublishSnapshot(payload:Record<string,unknown>):SnapshotResult{
  const s=payload.publish_snapshot;const problems:string[]=[];
  if(!isObj(s))return {ok:false,problems:["This request has no publish snapshot, so the account it would post to is unknown. It was filed before exact accounts were recorded."]};
  if(s.version!==2)problems.push(`Unsupported publish snapshot version ${JSON.stringify(s.version??null)}; this review understands version 2 only.`);
  const platform=s.platform;
  if(typeof platform!=="string"||!PLATFORMS.includes(platform))problems.push("Snapshot has no recognised platform.");
  const t=s.publish_target;let accountId="";
  if(!isObj(t)||Object.keys(t).length!==2||!("platform" in t)||!("account_id" in t))problems.push("Snapshot has no exact publish target (platform and account ID), so the destination is unknown.");
  else{
    if(t.platform!==platform)problems.push(`Target platform ${JSON.stringify(t.platform)} does not match the post platform ${JSON.stringify(platform??null)}.`);
    if(typeof platform==="string"&&validAccountId(platform,t.account_id))accountId=t.account_id as string;
    else problems.push("Publish target has a missing or malformed account ID.");
  }
  if(!nonEmpty(s.text))problems.push("Snapshot has no post text.");
  if(!nonEmpty(s.publish_at)||!Number.isFinite(Date.parse(s.publish_at))||!hasZone(s.publish_at))problems.push("Snapshot has no valid publish time with a timezone.");
  const media=strList(s.media_urls),alts=strList(s.alt_texts),chunks=strList(s.thread_chunks);
  if(!media||!alts||!chunks)problems.push("Snapshot media, alt text or thread parts are malformed.");
  if(s.link!==null&&s.link!==undefined&&typeof s.link!=="string")problems.push("Snapshot link is malformed.");
  if(typeof s.sponsored!=="boolean")problems.push("Snapshot does not say whether the post is sponsored.");
  if(nonEmpty(payload.platform)&&payload.platform!==platform)problems.push(`Platform mismatch: request says ${payload.platform}, snapshot says ${String(platform)}.`);
  if(typeof payload.copy==="string"&&payload.copy!==s.text)problems.push("Post text in the request differs from the snapshot text.");
  if(nonEmpty(payload.publish_at)&&nonEmpty(s.publish_at)&&!sameInstant(payload.publish_at,s.publish_at))problems.push("Publish time in the request differs from the snapshot time.");
  if(typeof payload.sponsored==="boolean"&&payload.sponsored!==s.sponsored)problems.push("Sponsored flag in the request differs from the snapshot.");
  if(problems.length)return {ok:false,problems};
  return {ok:true,snapshot:{platform:platform as string,accountId,format:nonEmpty(s.format)?s.format:null,text:s.text as string,publishAt:s.publish_at as string,
    mediaUrls:media!,altTexts:alts!,threadChunks:chunks!,link:typeof s.link==="string"?s.link:null,sponsored:s.sponsored as boolean}};
}
