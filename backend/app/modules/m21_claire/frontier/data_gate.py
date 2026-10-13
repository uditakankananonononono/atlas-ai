from __future__ import annotations
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import hashlib, json, os, re

_EMAIL=re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",re.I)
_PHONE=re.compile(r"(?<!\w)(?:\+?\d[\d ()-]{7,}\d)(?!\w)")
_DEFAULT_LICENSES={"cc0-1.0","cc-by-4.0","apache-2.0","mit","bsd-3-clause","bsd-2-clause","isc"}

class TrainingDataGate:
    """Consent/licence/provenance gate and group-safe train/validation/confirmation splitter.

    This prevents one source lineage from appearing across splits. It does not replace
    legal review or certify that a dataset's declared licence is accurate.
    """
    def __init__(self, *, seed: str="claire-frontier-v1", allowed_licenses: set[str] | None=None, export_root: str | Path | None=None):
        self._root_id=None; self._export_root=None
        self.export_root=export_root
        self.seed=seed; self.allowed_licenses={x.casefold() for x in (_DEFAULT_LICENSES if allowed_licenses is None else allowed_licenses)}
        self.rows=[]; self.rejections=[]; self._content_hashes=set(); self._group_splits={}

    def add(self, *, text: str, source_url: str, source_group: str, license_name: str,
            permission_to_use: bool, permitted_uses: list[str], purpose: str="training",
            published_at: str | None=None, reviewed_personal_data: bool=False) -> bool:
        def reject(reason): self.rejections.append({"reason":reason,"source_url":source_url[:300],"source_group":source_group[:100]}); return False
        if not text.strip() or len(text)>1_000_000: return reject("empty_or_overlarge_text")
        if not source_url.startswith(("https://","local-user-approved://")): return reject("missing_approved_provenance")
        if not source_group.strip(): return reject("source_group_required")
        if not license_name.strip() or license_name.casefold() not in self.allowed_licenses: return reject("license_not_allowlisted_for_configured_use")
        if permission_to_use is not True: return reject("explicit_permission_missing")
        uses={u.casefold() for u in permitted_uses}
        if purpose not in {"training","evaluation","retrieval"}: return reject("unknown_purpose")
        if purpose not in uses: return reject("purpose_not_permitted_by_source")
        found=[]
        if _EMAIL.search(text): found.append("email")
        if _PHONE.search(text): found.append("phone")
        if found and not reviewed_personal_data: return reject("possible_personal_data_requires_review")
        digest=hashlib.sha256(text.encode("utf-8")).hexdigest()
        if digest in self._content_hashes: return reject("duplicate_content")
        if source_group not in self._group_splits:
            slot=int(hashlib.sha256((self.seed+"\0"+source_group).encode()).hexdigest()[:8],16)%100
            self._group_splits[source_group]="train" if slot<70 else "validation" if slot<85 else "confirmation"
        split=self._group_splits[source_group]
        self._content_hashes.add(digest)
        self.rows.append({"text":text,"source_url":source_url,"source_group":source_group,"license":license_name,
            "permission_to_use":True,"permitted_uses":sorted(uses),"purpose":purpose,"split":split,
            "published_at":published_at,"personal_data_reviewed":reviewed_personal_data,"sha256":digest})
        return True

    def validate(self) -> dict[str,Any]:
        groups_by_split={}
        counts=Counter()
        for row in self.rows:
            counts[(row["purpose"],row["split"])]+=1
            groups_by_split.setdefault(row["source_group"],set()).add(row["split"])
        leaks=[g for g,splits in groups_by_split.items() if len(splits)>1]
        illegal=[r["sha256"] for r in self.rows if not r["permission_to_use"] or r["purpose"] not in r["permitted_uses"]]
        return {"valid":not leaks and not illegal,"record_count":len(self.rows),"rejected_count":len(self.rejections),
            "counts":{f"{purpose}:{split}":n for (purpose,split),n in sorted(counts.items())},
            "source_group_leaks":leaks,"invalid_permission_records":illegal,
            "confirmation_warning":"Group-hash split may be imbalanced on small corpora; verify minimum counts before any experiment."}

    @property
    def export_root(self) -> Path | None: return self._export_root

    @export_root.setter
    def export_root(self, value) -> None:
        """Resolve once and pin the root directory's identity (device, inode)."""
        if value is None: self._export_root=None; self._root_id=None; return
        root=Path(value).resolve()
        st=os.stat(root)  # must exist
        if not os.path.isdir(root): raise ValueError("export_root must be a directory")
        self._export_root=root; self._root_id=(st.st_dev,st.st_ino)

    def _open_dir_inside_root(self, parts) -> int:
        """Walk from the root one component at a time with O_NOFOLLOW so a symlinked
        directory cannot redirect output, even if swapped after validation."""
        flags=os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW
        try: fd=os.open(self.export_root,flags)
        except OSError as e: raise ValueError("export_root is missing or is now a symlink") from e
        st=os.fstat(fd)
        if (st.st_dev,st.st_ino)!=self._root_id:
            os.close(fd); raise ValueError("export_root identity changed since configuration")
        try:
            for part in parts:
                try: os.mkdir(part,0o700,dir_fd=fd)
                except FileExistsError: pass
                try: nxt=os.open(part,flags,dir_fd=fd)
                except OSError as e: raise ValueError("export directory component is a symlink or unreadable") from e
                os.close(fd); fd=nxt
            return fd
        except BaseException:
            os.close(fd); raise

    @staticmethod
    def _write_nofollow(dir_fd: int, name: str, data: bytes) -> None:
        try: fd=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW,0o600,dir_fd=dir_fd)
        except OSError as e: raise ValueError(f"refusing to write {name}: symlink or unwritable") from e
        with os.fdopen(fd,"wb") as f: f.write(data)

    def export(self, path: str | Path) -> dict[str,Any]:
        report=self.validate()
        if not report["valid"]: raise ValueError("refusing export: dataset gate failed")
        # Do not export rows lacking training permission in the train split.
        training=[r for r in self.rows if r["split"]=="train" and r["purpose"]=="training" and "training" in r["permitted_uses"]]
        if self.export_root is None: raise ValueError("export_root must be configured to export")
        rel=Path(path)
        if rel.is_absolute():
            try: rel=rel.relative_to(self.export_root)
            except ValueError as e: raise ValueError("export path must stay inside export_root") from e
        if not rel.parts or any(part in {"", ".", ".."} for part in rel.parts):
            raise ValueError("export path must be a plain relative path inside export_root")
        payload="".join(json.dumps({"text":row["text"]},ensure_ascii=False)+"\n" for row in training).encode("utf-8")
        digest=hashlib.sha256(payload).hexdigest()
        manifest={**report,"created_at":datetime.now(timezone.utc).isoformat(),"dataset_sha256":digest,"dataset_file":rel.name,
            "training_rows_exported":len(training),"rows":[{k:v for k,v in r.items() if k!="text"} for r in self.rows],
            "rejections":self.rejections,"not_a_legal_certification":True}
        manifest_bytes=json.dumps(manifest,indent=2).encode("utf-8")
        dfd=self._open_dir_inside_root(rel.parts[:-1])
        try:
            self._write_nofollow(dfd,rel.name,payload)
            self._write_nofollow(dfd,rel.name+".manifest.json",manifest_bytes)
        finally: os.close(dfd)
        return manifest
