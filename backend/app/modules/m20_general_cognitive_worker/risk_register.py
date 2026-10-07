"""Tenant-scoped risk review revisions. Completeness is not approval or evidence truth."""
from uuid import uuid4
from datetime import datetime, timezone
import copy
import sqlalchemy as sa
from .sql_repository import Base
from .foresight import PremortemEngine


class RiskRegisterRow(Base):
    __tablename__ = 'm20_risk_registers'
    tenant_id = sa.Column(sa.String, primary_key=True)
    id = sa.Column(sa.String, primary_key=True)
    revision = sa.Column(sa.Integer, nullable=False)
    goal = sa.Column(sa.Text, nullable=False)
    updated_at = sa.Column(sa.DateTime(timezone=True), nullable=False)


class RiskRevisionRow(Base):
    __tablename__ = 'm20_risk_revisions'
    tenant_id = sa.Column(sa.String, primary_key=True)
    register_id = sa.Column(sa.String, primary_key=True)
    revision = sa.Column(sa.Integer, primary_key=True)
    report_json = sa.Column(sa.JSON, nullable=False)
    created_at = sa.Column(sa.DateTime(timezone=True), nullable=False)


class DurableRiskRegister:
    def __init__(self, repo):
        self.repo = repo

    def create(self, *, goal, risks):
        report = PremortemEngine().assess_register(goal=goal, risks=risks)
        identifier = str(uuid4()); now = datetime.now(timezone.utc)
        with self.repo._session() as session:
            session.add(RiskRegisterRow(tenant_id=self.repo.tenant_id, id=identifier, revision=1, goal=goal, updated_at=now))
            session.add(RiskRevisionRow(tenant_id=self.repo.tenant_id, register_id=identifier, revision=1, report_json=report, created_at=now))
            session.commit()
        return {'id': identifier, 'revision': 1, 'report': copy.deepcopy(report)}

    def get(self, identifier):
        with self.repo._session() as session:
            row = session.get(RiskRegisterRow, (self.repo.tenant_id, identifier))
            if row is None: return None
            revision = session.get(RiskRevisionRow, (self.repo.tenant_id, identifier, row.revision))
            return {'id': identifier, 'revision': row.revision, 'report': copy.deepcopy(revision.report_json)}

    def revise(self, identifier, *, expected_revision, risks):
        if type(expected_revision) is not int or expected_revision < 1:
            raise ValueError('expected_revision must be a positive exact integer')
        with self.repo._session() as session:
            row = session.get(RiskRegisterRow, (self.repo.tenant_id, identifier))
            if row is None: raise KeyError(identifier)
            report = PremortemEngine().assess_register(goal=row.goal, risks=risks)
            now = datetime.now(timezone.utc); next_revision = expected_revision + 1
            updated = session.execute(sa.update(RiskRegisterRow).where(
                RiskRegisterRow.tenant_id == self.repo.tenant_id, RiskRegisterRow.id == identifier,
                RiskRegisterRow.revision == expected_revision).values(revision=next_revision, updated_at=now))
            if updated.rowcount != 1:
                raise ValueError('revision conflict; reload current register')
            session.add(RiskRevisionRow(tenant_id=self.repo.tenant_id, register_id=identifier, revision=next_revision, report_json=report, created_at=now))
            session.commit()
        return {'id': identifier, 'revision': next_revision, 'report': copy.deepcopy(report)}

    def history(self, identifier):
        with self.repo._session() as session:
            rows = session.scalars(sa.select(RiskRevisionRow).where(
                RiskRevisionRow.tenant_id == self.repo.tenant_id, RiskRevisionRow.register_id == identifier).order_by(RiskRevisionRow.revision)).all()
            return [{'id': identifier, 'revision': row.revision, 'report': copy.deepcopy(row.report_json)} for row in rows]
