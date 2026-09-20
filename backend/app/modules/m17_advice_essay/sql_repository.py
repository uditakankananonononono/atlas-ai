"""PostgreSQL persistence for Module 17 using a DB-API compatible connection."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any, Protocol
from uuid import UUID

from .schemas import AdviceSource, AdviceTip, EssayConcept, IdentityMaterial


class Cursor(Protocol):
    def execute(self, query: str, params: Sequence[Any] | None = None) -> Any: ...
    def fetchall(self) -> list[Any]: ...
    def fetchone(self) -> Any | None: ...


class Connection(Protocol):
    def cursor(self) -> Cursor: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...


DDL = """
CREATE TABLE IF NOT EXISTS m17_advice_sources (
    id UUID PRIMARY KEY,
    owner_id UUID NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS m17_sources_owner_idx ON m17_advice_sources(owner_id);
CREATE TABLE IF NOT EXISTS m17_identity_materials (
    id UUID PRIMARY KEY,
    owner_id UUID NOT NULL,
    user_confirmed BOOLEAN NOT NULL CHECK (user_confirmed),
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS m17_materials_owner_idx ON m17_identity_materials(owner_id);
CREATE TABLE IF NOT EXISTS m17_advice_tips (
    id UUID PRIMARY KEY,
    owner_id UUID NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS m17_tips_owner_idx ON m17_advice_tips(owner_id);
CREATE TABLE IF NOT EXISTS m17_essay_concepts (
    id UUID PRIMARY KEY,
    owner_id UUID NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS m17_concepts_owner_idx ON m17_essay_concepts(owner_id);
"""


class SqlModule17Repository:
    def __init__(self, connection: Connection) -> None:
        self.connection = connection

    def create_schema(self) -> None:
        cursor = self.connection.cursor()
        try:
            cursor.execute(DDL)
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise

    def add_source(self, source: AdviceSource) -> AdviceSource:
        self._insert("m17_advice_sources", source.id, source.owner_id, source.model_dump(mode="json"))
        return source

    def list_sources(self, owner_id: UUID) -> list[AdviceSource]:
        return [AdviceSource.model_validate(row[0]) for row in self._list("m17_advice_sources", owner_id)]

    def add_material(self, material: IdentityMaterial) -> IdentityMaterial:
        if not material.user_confirmed:
            raise ValueError("identity material must be user-confirmed")
        self._insert(
            "m17_identity_materials",
            material.id,
            material.owner_id,
            material.model_dump(mode="json"),
            extra_columns="user_confirmed",
            extra_values=[True],
        )
        return material

    def list_materials(self, owner_id: UUID, ids: Sequence[UUID]) -> list[IdentityMaterial]:
        if not ids:
            return []
        cursor = self.connection.cursor()
        placeholders = ", ".join(["%s"] * len(ids))
        cursor.execute(
            f"SELECT payload FROM m17_identity_materials WHERE owner_id = %s "
            f"AND user_confirmed = TRUE AND id IN ({placeholders}) ORDER BY created_at, id",
            [str(owner_id), *[str(value) for value in ids]],
        )
        return [IdentityMaterial.model_validate(self._payload(row[0])) for row in cursor.fetchall()]

    def add_tip(self, tip: AdviceTip) -> AdviceTip:
        self._insert("m17_advice_tips", tip.id, tip.owner_id, tip.model_dump(mode="json"))
        return tip

    def list_tips(self, owner_id: UUID) -> list[AdviceTip]:
        return [AdviceTip.model_validate(row[0]) for row in self._list("m17_advice_tips", owner_id)]

    def add_concept(self, concept: EssayConcept) -> EssayConcept:
        self._insert("m17_essay_concepts", concept.id, concept.owner_id, concept.model_dump(mode="json"))
        return concept

    def _insert(
        self,
        table: str,
        item_id: UUID,
        owner_id: UUID,
        payload: dict[str, Any],
        extra_columns: str = "",
        extra_values: Sequence[Any] = (),
    ) -> None:
        allowed = {
            "m17_advice_sources",
            "m17_identity_materials",
            "m17_advice_tips",
            "m17_essay_concepts",
        }
        if table not in allowed:
            raise ValueError("unsupported table")
        columns = f", {extra_columns}" if extra_columns else ""
        placeholders = ", %s" if extra_columns else ""
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                f"INSERT INTO {table} (id, owner_id, payload{columns}) VALUES (%s, %s, %s::jsonb{placeholders})",
                [str(item_id), str(owner_id), json.dumps(payload), *extra_values],
            )
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise

    def _list(self, table: str, owner_id: UUID) -> list[tuple[Any]]:
        allowed = {"m17_advice_sources", "m17_advice_tips"}
        if table not in allowed:
            raise ValueError("unsupported table")
        cursor = self.connection.cursor()
        cursor.execute(f"SELECT payload FROM {table} WHERE owner_id = %s ORDER BY created_at, id", [str(owner_id)])
        return [(self._payload(row[0]),) for row in cursor.fetchall()]

    @staticmethod
    def _payload(value: Any) -> Any:
        return json.loads(value) if isinstance(value, str) else value
