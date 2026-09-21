"""initial production schema"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = '96ad3c0c61e0'
down_revision = '0001_baseline'
branch_labels = None
depends_on = None
def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    # Generated from the complete imported SQLAlchemy metadata.
    op.create_table('collected_records',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('source_key', sa.String(length=300), nullable=False),
    sa.Column('canonical_url', sa.Text(), nullable=False),
    sa.Column('content_hash', sa.String(length=64), nullable=False),
    sa.Column('payload', sa.JSON(), nullable=False),
    sa.Column('collected_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant_id', 'content_hash')
    )
    op.create_index(op.f('ix_collected_records_content_hash'), 'collected_records', ['content_hash'], unique=False)
    op.create_index(op.f('ix_collected_records_source_key'), 'collected_records', ['source_key'], unique=False)
    op.create_index(op.f('ix_collected_records_tenant_id'), 'collected_records', ['tenant_id'], unique=False)
    op.create_table('collection_runs',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('source_key', sa.String(length=300), nullable=False),
    sa.Column('status', sa.String(length=30), nullable=False),
    sa.Column('requests', sa.Integer(), nullable=False),
    sa.Column('records_new', sa.Integer(), nullable=False),
    sa.Column('estimated_cost_usd', sa.Float(), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('detail', sa.JSON(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_collection_runs_source_key'), 'collection_runs', ['source_key'], unique=False)
    op.create_index(op.f('ix_collection_runs_tenant_id'), 'collection_runs', ['tenant_id'], unique=False)
    op.create_table('collection_sources',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('source_key', sa.String(length=300), nullable=False),
    sa.Column('collector_type', sa.String(length=40), nullable=False),
    sa.Column('priority', sa.Integer(), nullable=False),
    sa.Column('cadence_seconds', sa.Integer(), nullable=False),
    sa.Column('enabled', sa.Boolean(), nullable=False),
    sa.Column('cost_per_1000_requests_usd', sa.Float(), nullable=False),
    sa.Column('daily_request_cap', sa.Integer(), nullable=False),
    sa.Column('config', sa.JSON(), nullable=False),
    sa.Column('next_run_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('throttle_until', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant_id', 'source_key')
    )
    op.create_index(op.f('ix_collection_sources_collector_type'), 'collection_sources', ['collector_type'], unique=False)
    op.create_index(op.f('ix_collection_sources_next_run_at'), 'collection_sources', ['next_run_at'], unique=False)
    op.create_index(op.f('ix_collection_sources_priority'), 'collection_sources', ['priority'], unique=False)
    op.create_index(op.f('ix_collection_sources_tenant_id'), 'collection_sources', ['tenant_id'], unique=False)
    op.create_table('discovery_candidates',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('platform', sa.String(length=30), nullable=False),
    sa.Column('account_key', sa.String(length=300), nullable=False),
    sa.Column('profile_url', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=30), nullable=False),
    sa.Column('evidence', sa.JSON(), nullable=False),
    sa.Column('discovered_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant_id', 'platform', 'account_key')
    )
    op.create_index(op.f('ix_discovery_candidates_platform'), 'discovery_candidates', ['platform'], unique=False)
    op.create_index(op.f('ix_discovery_candidates_status'), 'discovery_candidates', ['status'], unique=False)
    op.create_index(op.f('ix_discovery_candidates_tenant_id'), 'discovery_candidates', ['tenant_id'], unique=False)
    op.create_table('m00_approval_effects',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('approval_id', sa.String(length=36), nullable=False),
    sa.Column('effect_id', sa.String(length=200), nullable=False),
    sa.Column('request_hash', sa.String(length=64), nullable=False),
    sa.Column('actor', sa.String(length=120), nullable=False),
    sa.Column('consumed_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('approval_id'),
    sa.UniqueConstraint('effect_id')
    )
    op.create_index(op.f('ix_m00_approval_effects_approval_id'), 'm00_approval_effects', ['approval_id'], unique=False)
    op.create_index(op.f('ix_m00_approval_effects_effect_id'), 'm00_approval_effects', ['effect_id'], unique=False)
    op.create_table('m00_approval_events',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('approval_id', sa.String(length=36), nullable=False),
    sa.Column('event', sa.String(length=40), nullable=False),
    sa.Column('actor', sa.String(length=120), nullable=True),
    sa.Column('at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_m00_approval_events_approval_id'), 'm00_approval_events', ['approval_id'], unique=False)
    op.create_table('m00_approval_idempotency',
    sa.Column('key', sa.String(length=200), nullable=False),
    sa.Column('request_hash', sa.String(length=64), nullable=False),
    sa.Column('approval_id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('key')
    )
    op.create_index(op.f('ix_m00_approval_idempotency_approval_id'), 'm00_approval_idempotency', ['approval_id'], unique=True)
    op.create_table('m00_approval_policies',
    sa.Column('id', sa.String(length=120), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('module_id', sa.Integer(), nullable=True),
    sa.Column('action_pattern', sa.String(length=200), nullable=False),
    sa.Column('effect', sa.String(length=20), nullable=False),
    sa.Column('priority', sa.Integer(), nullable=False),
    sa.Column('enabled', sa.Boolean(), nullable=False),
    sa.Column('conditions', sa.JSON(), nullable=False),
    sa.Column('review_ttl_seconds', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_m00_approval_policies_enabled'), 'm00_approval_policies', ['enabled'], unique=False)
    op.create_index(op.f('ix_m00_approval_policies_module_id'), 'm00_approval_policies', ['module_id'], unique=False)
    op.create_index(op.f('ix_m00_approval_policies_priority'), 'm00_approval_policies', ['priority'], unique=False)
    op.create_table('m00_approval_requests',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=120), nullable=False),
    sa.Column('module_id', sa.Integer(), nullable=False),
    sa.Column('action_type', sa.String(length=100), nullable=False),
    sa.Column('payload', sa.JSON(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('approved_by', sa.String(length=120), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_m00_approval_requests_action_type'), 'm00_approval_requests', ['action_type'], unique=False)
    op.create_index(op.f('ix_m00_approval_requests_status'), 'm00_approval_requests', ['status'], unique=False)
    op.create_index(op.f('ix_m00_approval_requests_user_id'), 'm00_approval_requests', ['user_id'], unique=False)
    op.create_table('m01_opportunities',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('source_id', sa.String(length=100), nullable=False),
    sa.Column('title', sa.String(length=500), nullable=False),
    sa.Column('url', sa.String(length=2000), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('deadline', sa.DateTime(timezone=True), nullable=True),
    sa.Column('opportunity_type', sa.String(length=30), nullable=False),
    sa.Column('match_score', sa.Float(), nullable=False),
    sa.Column('expected_impact', sa.Float(), nullable=False),
    sa.Column('tags', sa.JSON(), nullable=False),
    sa.Column('first_seen', sa.DateTime(timezone=True), nullable=False),
    sa.Column('last_seen', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_m01_opportunities_match_score'), 'm01_opportunities', ['match_score'], unique=False)
    op.create_index(op.f('ix_m01_opportunities_opportunity_type'), 'm01_opportunities', ['opportunity_type'], unique=False)
    op.create_index(op.f('ix_m01_opportunities_source_id'), 'm01_opportunities', ['source_id'], unique=False)
    op.create_index(op.f('ix_m01_opportunities_url'), 'm01_opportunities', ['url'], unique=False)
    op.create_table('m02_competitions',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('competition_id', sa.String(length=36), nullable=False),
    sa.Column('data', sa.JSON(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant_id', 'competition_id')
    )
    op.create_index(op.f('ix_m02_competitions_competition_id'), 'm02_competitions', ['competition_id'], unique=False)
    op.create_index(op.f('ix_m02_competitions_tenant_id'), 'm02_competitions', ['tenant_id'], unique=False)
    op.create_table('m02_corpus_onboarding',
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('completed', sa.Boolean(), nullable=False),
    sa.Column('skipped', sa.Boolean(), nullable=False),
    sa.Column('document_types', sa.JSON(), nullable=False),
    sa.Column('source_ids', sa.JSON(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('tenant_id')
    )
    op.create_table('m02_profile_documents',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('source_type', sa.String(length=40), nullable=False),
    sa.Column('source_id', sa.String(length=500), nullable=False),
    sa.Column('locator', sa.String(length=1000), nullable=False),
    sa.Column('title', sa.Text(), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('provenance', sa.JSON(), nullable=False),
    sa.Column('embedding', sa.JSON(), nullable=False),
    sa.Column('indexed_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant_id', 'source_type', 'source_id', 'locator')
    )
    op.create_index(op.f('ix_m02_profile_documents_tenant_id'), 'm02_profile_documents', ['tenant_id'], unique=False)
    op.create_table('m03_funded_awards',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('source', sa.String(length=40), nullable=False),
    sa.Column('award_id', sa.String(length=160), nullable=False),
    sa.Column('title', sa.Text(), nullable=False),
    sa.Column('abstract', sa.Text(), nullable=False),
    sa.Column('url', sa.Text(), nullable=False),
    sa.Column('provenance', sa.JSON(), nullable=False),
    sa.Column('collected_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant_id', 'source', 'award_id')
    )
    op.create_index(op.f('ix_m03_funded_awards_award_id'), 'm03_funded_awards', ['award_id'], unique=False)
    op.create_index(op.f('ix_m03_funded_awards_source'), 'm03_funded_awards', ['source'], unique=False)
    op.create_index(op.f('ix_m03_funded_awards_tenant_id'), 'm03_funded_awards', ['tenant_id'], unique=False)
    op.create_table('m04_surveillance_papers',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('paper_id', sa.String(length=200), nullable=False),
    sa.Column('title', sa.Text(), nullable=False),
    sa.Column('abstract', sa.Text(), nullable=False),
    sa.Column('source', sa.String(length=40), nullable=False),
    sa.Column('url', sa.Text(), nullable=True),
    sa.Column('published_at', sa.String(length=100), nullable=True),
    sa.Column('keywords', sa.JSON(), nullable=False),
    sa.Column('embedding', sa.JSON(), nullable=False),
    sa.Column('collected_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant_id', 'paper_id')
    )
    op.create_index(op.f('ix_m04_surveillance_papers_paper_id'), 'm04_surveillance_papers', ['paper_id'], unique=False)
    op.create_index(op.f('ix_m04_surveillance_papers_tenant_id'), 'm04_surveillance_papers', ['tenant_id'], unique=False)
    op.create_table('m05_campaigns',
    sa.Column('pk', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('project_id', sa.String(length=120), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('goal', sa.Text(), nullable=False),
    sa.Column('audience', sa.String(length=40), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('max_follow_ups', sa.Integer(), nullable=False),
    sa.Column('follow_up_window_days', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('pk'),
    sa.UniqueConstraint('tenant_id', 'id')
    )
    op.create_index(op.f('ix_m05_campaigns_id'), 'm05_campaigns', ['id'], unique=False)
    op.create_index(op.f('ix_m05_campaigns_project_id'), 'm05_campaigns', ['project_id'], unique=False)
    op.create_index(op.f('ix_m05_campaigns_status'), 'm05_campaigns', ['status'], unique=False)
    op.create_index(op.f('ix_m05_campaigns_tenant_id'), 'm05_campaigns', ['tenant_id'], unique=False)
    op.create_table('m05_contact_changes',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('contact_id', sa.String(length=36), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('changed_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('changes', sa.JSON(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_m05_contact_changes_contact_id'), 'm05_contact_changes', ['contact_id'], unique=False)
    op.create_index(op.f('ix_m05_contact_changes_tenant_id'), 'm05_contact_changes', ['tenant_id'], unique=False)
    op.create_table('m05_contacts',
    sa.Column('pk', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('project_id', sa.String(length=120), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('email', sa.String(length=320), nullable=True),
    sa.Column('institution', sa.String(length=300), nullable=True),
    sa.Column('research_topics', sa.JSON(), nullable=False),
    sa.Column('profile_url', sa.Text(), nullable=True),
    sa.Column('metadata_json', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('pk'),
    sa.UniqueConstraint('tenant_id', 'id')
    )
    op.create_index(op.f('ix_m05_contacts_email'), 'm05_contacts', ['email'], unique=False)
    op.create_index(op.f('ix_m05_contacts_id'), 'm05_contacts', ['id'], unique=False)
    op.create_index(op.f('ix_m05_contacts_project_id'), 'm05_contacts', ['project_id'], unique=False)
    op.create_index(op.f('ix_m05_contacts_tenant_id'), 'm05_contacts', ['tenant_id'], unique=False)
    op.create_table('m05_message_events',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('message_id', sa.String(length=36), nullable=False),
    sa.Column('event', sa.String(length=60), nullable=False),
    sa.Column('actor', sa.String(length=120), nullable=True),
    sa.Column('at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('details', sa.JSON(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_m05_message_events_message_id'), 'm05_message_events', ['message_id'], unique=False)
    op.create_index(op.f('ix_m05_message_events_tenant_id'), 'm05_message_events', ['tenant_id'], unique=False)
    op.create_table('m05_messages',
    sa.Column('pk', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('campaign_id', sa.String(length=36), nullable=False),
    sa.Column('contact_id', sa.String(length=36), nullable=False),
    sa.Column('sequence', sa.Integer(), nullable=False),
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.Column('subject', sa.String(length=500), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('approval_id', sa.String(length=36), nullable=True),
    sa.Column('provider', sa.String(length=40), nullable=True),
    sa.Column('model', sa.String(length=120), nullable=True),
    sa.Column('thread_id', sa.String(length=200), nullable=True),
    sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('pk'),
    sa.UniqueConstraint('tenant_id', 'id')
    )
    op.create_index(op.f('ix_m05_messages_campaign_id'), 'm05_messages', ['campaign_id'], unique=False)
    op.create_index(op.f('ix_m05_messages_contact_id'), 'm05_messages', ['contact_id'], unique=False)
    op.create_index(op.f('ix_m05_messages_id'), 'm05_messages', ['id'], unique=False)
    op.create_index(op.f('ix_m05_messages_status'), 'm05_messages', ['status'], unique=False)
    op.create_index(op.f('ix_m05_messages_tenant_id'), 'm05_messages', ['tenant_id'], unique=False)
    op.create_table('m06_social_ab_tests',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('item_id', sa.String(length=36), nullable=False),
    sa.Column('data', sa.JSON(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant_id', 'item_id')
    )
    op.create_index(op.f('ix_m06_social_ab_tests_item_id'), 'm06_social_ab_tests', ['item_id'], unique=False)
    op.create_index(op.f('ix_m06_social_ab_tests_tenant_id'), 'm06_social_ab_tests', ['tenant_id'], unique=False)
    op.create_table('m06_social_artifacts',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('item_id', sa.String(length=36), nullable=False),
    sa.Column('kind', sa.String(length=60), nullable=False),
    sa.Column('data', sa.JSON(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant_id', 'item_id')
    )
    op.create_index(op.f('ix_m06_social_artifacts_item_id'), 'm06_social_artifacts', ['item_id'], unique=False)
    op.create_index(op.f('ix_m06_social_artifacts_kind'), 'm06_social_artifacts', ['kind'], unique=False)
    op.create_index(op.f('ix_m06_social_artifacts_tenant_id'), 'm06_social_artifacts', ['tenant_id'], unique=False)
    op.create_table('m06_social_plans',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('item_id', sa.String(length=36), nullable=False),
    sa.Column('data', sa.JSON(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant_id', 'item_id')
    )
    op.create_index(op.f('ix_m06_social_plans_item_id'), 'm06_social_plans', ['item_id'], unique=False)
    op.create_index(op.f('ix_m06_social_plans_tenant_id'), 'm06_social_plans', ['tenant_id'], unique=False)
    op.create_table('m06_social_publishes',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('item_id', sa.String(length=36), nullable=False),
    sa.Column('data', sa.JSON(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant_id', 'item_id')
    )
    op.create_index(op.f('ix_m06_social_publishes_item_id'), 'm06_social_publishes', ['item_id'], unique=False)
    op.create_index(op.f('ix_m06_social_publishes_tenant_id'), 'm06_social_publishes', ['tenant_id'], unique=False)
    op.create_table('m06_social_reports',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('item_id', sa.String(length=36), nullable=False),
    sa.Column('data', sa.JSON(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant_id', 'item_id')
    )
    op.create_index(op.f('ix_m06_social_reports_item_id'), 'm06_social_reports', ['item_id'], unique=False)
    op.create_index(op.f('ix_m06_social_reports_tenant_id'), 'm06_social_reports', ['tenant_id'], unique=False)
    op.create_table('m06_social_schedules',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('item_id', sa.String(length=36), nullable=False),
    sa.Column('status', sa.String(length=30), nullable=False),
    sa.Column('data', sa.JSON(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant_id', 'item_id')
    )
    op.create_index(op.f('ix_m06_social_schedules_item_id'), 'm06_social_schedules', ['item_id'], unique=False)
    op.create_index(op.f('ix_m06_social_schedules_status'), 'm06_social_schedules', ['status'], unique=False)
    op.create_index(op.f('ix_m06_social_schedules_tenant_id'), 'm06_social_schedules', ['tenant_id'], unique=False)
    op.create_table('m06_social_snapshots',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('item_id', sa.String(length=36), nullable=False),
    sa.Column('platform', sa.String(length=30), nullable=False),
    sa.Column('data', sa.JSON(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant_id', 'item_id')
    )
    op.create_index(op.f('ix_m06_social_snapshots_item_id'), 'm06_social_snapshots', ['item_id'], unique=False)
    op.create_index(op.f('ix_m06_social_snapshots_platform'), 'm06_social_snapshots', ['platform'], unique=False)
    op.create_index(op.f('ix_m06_social_snapshots_tenant_id'), 'm06_social_snapshots', ['tenant_id'], unique=False)
    op.create_table('m07_artifacts',
    sa.Column('pk', sa.Integer(), nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('brand_id', sa.String(length=36), nullable=False),
    sa.Column('kind', sa.String(length=40), nullable=False),
    sa.Column('content_type', sa.String(length=120), nullable=False),
    sa.Column('content', sa.LargeBinary(), nullable=False),
    sa.Column('sha256', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('metadata_json', sa.JSON(), nullable=False),
    sa.PrimaryKeyConstraint('pk')
    )
    op.create_index(op.f('ix_m07_artifacts_brand_id'), 'm07_artifacts', ['brand_id'], unique=False)
    op.create_index(op.f('ix_m07_artifacts_id'), 'm07_artifacts', ['id'], unique=False)
    op.create_index(op.f('ix_m07_artifacts_tenant_id'), 'm07_artifacts', ['tenant_id'], unique=False)
    op.create_table('m07_brands',
    sa.Column('pk', sa.Integer(), nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('mission', sa.Text(), nullable=False),
    sa.Column('public_url', sa.Text(), nullable=False),
    sa.Column('contact_api', sa.String(length=40), nullable=False),
    sa.Column('audience_tags', sa.JSON(), nullable=False),
    sa.Column('alignment_score', sa.Float(), nullable=False),
    sa.Column('alignment_reasons', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('pk')
    )
    op.create_index(op.f('ix_m07_brands_id'), 'm07_brands', ['id'], unique=False)
    op.create_index(op.f('ix_m07_brands_tenant_id'), 'm07_brands', ['tenant_id'], unique=False)
    op.create_table('m07_partnership_events',
    sa.Column('pk', sa.Integer(), nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('brand_id', sa.String(length=36), nullable=False),
    sa.Column('kind', sa.String(length=40), nullable=False),
    sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('data', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('pk')
    )
    op.create_index(op.f('ix_m07_partnership_events_brand_id'), 'm07_partnership_events', ['brand_id'], unique=False)
    op.create_index(op.f('ix_m07_partnership_events_id'), 'm07_partnership_events', ['id'], unique=False)
    op.create_index(op.f('ix_m07_partnership_events_tenant_id'), 'm07_partnership_events', ['tenant_id'], unique=False)
    op.create_table('m08_builds',
    sa.Column('pk', sa.Integer(), nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('project_id', sa.String(length=120), nullable=False),
    sa.Column('kind', sa.String(length=40), nullable=False),
    sa.Column('archive', sa.LargeBinary(), nullable=False),
    sa.Column('manifest', sa.JSON(), nullable=False),
    sa.Column('sha256', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('pk')
    )
    op.create_index(op.f('ix_m08_builds_id'), 'm08_builds', ['id'], unique=False)
    op.create_index(op.f('ix_m08_builds_project_id'), 'm08_builds', ['project_id'], unique=False)
    op.create_index(op.f('ix_m08_builds_tenant_id'), 'm08_builds', ['tenant_id'], unique=False)
    op.create_table('m09_audit',
    sa.Column('pk', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('actor_id', sa.String(length=120), nullable=False),
    sa.Column('action', sa.String(length=80), nullable=False),
    sa.Column('entity_id', sa.String(length=36), nullable=False),
    sa.Column('detail', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('pk')
    )
    op.create_index(op.f('ix_m09_audit_tenant_id'), 'm09_audit', ['tenant_id'], unique=False)
    op.create_table('m09_edges',
    sa.Column('pk', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('source_id', sa.String(length=36), nullable=False),
    sa.Column('target_id', sa.String(length=36), nullable=False),
    sa.Column('relationship', sa.String(length=40), nullable=False),
    sa.Column('rationale', sa.Text(), nullable=True),
    sa.Column('evidence', sa.JSON(), nullable=False),
    sa.Column('confidence', sa.Float(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('pk'),
    sa.UniqueConstraint('tenant_id', 'source_id', 'target_id', 'relationship', name='uq_m09_edge')
    )
    op.create_index(op.f('ix_m09_edges_id'), 'm09_edges', ['id'], unique=False)
    op.create_index(op.f('ix_m09_edges_source_id'), 'm09_edges', ['source_id'], unique=False)
    op.create_index(op.f('ix_m09_edges_target_id'), 'm09_edges', ['target_id'], unique=False)
    op.create_index(op.f('ix_m09_edges_tenant_id'), 'm09_edges', ['tenant_id'], unique=False)
    op.create_table('m09_nodes',
    sa.Column('pk', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('node_type', sa.String(length=40), nullable=False),
    sa.Column('title', sa.String(length=500), nullable=False),
    sa.Column('body', sa.Text(), nullable=True),
    sa.Column('source_uri', sa.Text(), nullable=True),
    sa.Column('source_module', sa.String(length=80), nullable=True),
    sa.Column('external_id', sa.String(length=500), nullable=True),
    sa.Column('metadata_json', sa.JSON(), nullable=False),
    sa.Column('embedding', sa.JSON(), nullable=True),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('pk'),
    sa.UniqueConstraint('tenant_id', 'source_module', 'external_id', name='uq_m09_external')
    )
    op.create_index(op.f('ix_m09_nodes_id'), 'm09_nodes', ['id'], unique=False)
    op.create_index(op.f('ix_m09_nodes_node_type'), 'm09_nodes', ['node_type'], unique=False)
    op.create_index(op.f('ix_m09_nodes_tenant_id'), 'm09_nodes', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_m09_nodes_title'), 'm09_nodes', ['title'], unique=False)
    op.create_table('m09_suggestions',
    sa.Column('pk', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('source_id', sa.String(length=36), nullable=False),
    sa.Column('target_id', sa.String(length=36), nullable=False),
    sa.Column('relationship', sa.String(length=40), nullable=False),
    sa.Column('score', sa.Float(), nullable=False),
    sa.Column('reasons', sa.JSON(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('pk'),
    sa.UniqueConstraint('tenant_id', 'source_id', 'target_id', 'relationship', name='uq_m09_suggestion')
    )
    op.create_index(op.f('ix_m09_suggestions_id'), 'm09_suggestions', ['id'], unique=False)
    op.create_index(op.f('ix_m09_suggestions_tenant_id'), 'm09_suggestions', ['tenant_id'], unique=False)
    op.create_table('m10_action_items',
    sa.Column('pk', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('message_id', sa.String(length=36), nullable=False),
    sa.Column('action', sa.Text(), nullable=False),
    sa.Column('deadline', sa.DateTime(timezone=True), nullable=True),
    sa.Column('related_entity', sa.String(length=300), nullable=True),
    sa.Column('confidence', sa.Float(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.PrimaryKeyConstraint('pk')
    )
    op.create_index(op.f('ix_m10_action_items_id'), 'm10_action_items', ['id'], unique=False)
    op.create_index(op.f('ix_m10_action_items_message_id'), 'm10_action_items', ['message_id'], unique=False)
    op.create_index(op.f('ix_m10_action_items_tenant_id'), 'm10_action_items', ['tenant_id'], unique=False)
    op.create_table('m10_email_drafts',
    sa.Column('pk', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('message_id', sa.String(length=36), nullable=False),
    sa.Column('approval_id', sa.String(length=36), nullable=False),
    sa.Column('to', sa.String(length=320), nullable=False),
    sa.Column('subject', sa.Text(), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('model', sa.String(length=120), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('pk')
    )
    op.create_index(op.f('ix_m10_email_drafts_approval_id'), 'm10_email_drafts', ['approval_id'], unique=False)
    op.create_index(op.f('ix_m10_email_drafts_id'), 'm10_email_drafts', ['id'], unique=False)
    op.create_index(op.f('ix_m10_email_drafts_message_id'), 'm10_email_drafts', ['message_id'], unique=False)
    op.create_index(op.f('ix_m10_email_drafts_tenant_id'), 'm10_email_drafts', ['tenant_id'], unique=False)
    op.create_table('m10_email_events',
    sa.Column('pk', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('entity', sa.String(length=40), nullable=False),
    sa.Column('entity_id', sa.String(length=64), nullable=False),
    sa.Column('event', sa.String(length=60), nullable=False),
    sa.Column('at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('details', sa.JSON(), nullable=False),
    sa.PrimaryKeyConstraint('pk')
    )
    op.create_index(op.f('ix_m10_email_events_entity_id'), 'm10_email_events', ['entity_id'], unique=False)
    op.create_index(op.f('ix_m10_email_events_tenant_id'), 'm10_email_events', ['tenant_id'], unique=False)
    op.create_table('m10_email_messages',
    sa.Column('pk', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('account_id', sa.String(length=36), nullable=False),
    sa.Column('gmail_id', sa.String(length=64), nullable=False),
    sa.Column('thread_id', sa.String(length=64), nullable=True),
    sa.Column('history_id', sa.String(length=40), nullable=True),
    sa.Column('subject', sa.Text(), nullable=False),
    sa.Column('sender', sa.String(length=320), nullable=False),
    sa.Column('recipients', sa.JSON(), nullable=False),
    sa.Column('snippet', sa.Text(), nullable=False),
    sa.Column('body_text', sa.Text(), nullable=False),
    sa.Column('received_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('labels', sa.JSON(), nullable=False),
    sa.Column('headers', sa.JSON(), nullable=False),
    sa.Column('category', sa.String(length=40), nullable=True),
    sa.Column('category_confidence', sa.Float(), nullable=False),
    sa.Column('embedding', sa.JSON(), nullable=True),
    sa.Column('unsubscribe_url', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('pk'),
    sa.UniqueConstraint('tenant_id', 'gmail_id')
    )
    op.create_index(op.f('ix_m10_email_messages_account_id'), 'm10_email_messages', ['account_id'], unique=False)
    op.create_index(op.f('ix_m10_email_messages_category'), 'm10_email_messages', ['category'], unique=False)
    op.create_index(op.f('ix_m10_email_messages_id'), 'm10_email_messages', ['id'], unique=False)
    op.create_index(op.f('ix_m10_email_messages_sender'), 'm10_email_messages', ['sender'], unique=False)
    op.create_index(op.f('ix_m10_email_messages_tenant_id'), 'm10_email_messages', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_m10_email_messages_thread_id'), 'm10_email_messages', ['thread_id'], unique=False)
    op.create_table('m10_gmail_accounts',
    sa.Column('pk', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('email_address', sa.String(length=320), nullable=False),
    sa.Column('encrypted_refresh_token', sa.Text(), nullable=False),
    sa.Column('history_id', sa.String(length=40), nullable=True),
    sa.Column('watch_expiration', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('pk'),
    sa.UniqueConstraint('tenant_id', 'email_address')
    )
    op.create_index(op.f('ix_m10_gmail_accounts_id'), 'm10_gmail_accounts', ['id'], unique=False)
    op.create_index(op.f('ix_m10_gmail_accounts_tenant_id'), 'm10_gmail_accounts', ['tenant_id'], unique=False)
    op.create_table('m11_calendar_events',
    sa.Column('pk', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('source_id', sa.String(length=36), nullable=False),
    sa.Column('uid', sa.String(length=200), nullable=False),
    sa.Column('summary', sa.Text(), nullable=False),
    sa.Column('start', sa.DateTime(timezone=True), nullable=True),
    sa.Column('end', sa.DateTime(timezone=True), nullable=True),
    sa.Column('location', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('pk'),
    sa.UniqueConstraint('tenant_id', 'source_id', 'uid')
    )
    op.create_index(op.f('ix_m11_calendar_events_id'), 'm11_calendar_events', ['id'], unique=False)
    op.create_index(op.f('ix_m11_calendar_events_source_id'), 'm11_calendar_events', ['source_id'], unique=False)
    op.create_index(op.f('ix_m11_calendar_events_tenant_id'), 'm11_calendar_events', ['tenant_id'], unique=False)
    op.create_table('m11_calendar_events_log',
    sa.Column('pk', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('entity', sa.String(length=40), nullable=False),
    sa.Column('entity_id', sa.String(length=64), nullable=False),
    sa.Column('event', sa.String(length=60), nullable=False),
    sa.Column('at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('details', sa.JSON(), nullable=False),
    sa.PrimaryKeyConstraint('pk')
    )
    op.create_index(op.f('ix_m11_calendar_events_log_entity_id'), 'm11_calendar_events_log', ['entity_id'], unique=False)
    op.create_index(op.f('ix_m11_calendar_events_log_tenant_id'), 'm11_calendar_events_log', ['tenant_id'], unique=False)
    op.create_table('m11_calendar_sources',
    sa.Column('pk', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('provider', sa.String(length=20), nullable=False),
    sa.Column('account_email', sa.String(length=320), nullable=False),
    sa.Column('calendar_ref', sa.Text(), nullable=False),
    sa.Column('encrypted_credentials', sa.Text(), nullable=False),
    sa.Column('sync_token', sa.Text(), nullable=True),
    sa.Column('watch_channel_id', sa.String(length=64), nullable=True),
    sa.Column('watch_channel_token', sa.String(length=64), nullable=True),
    sa.Column('watch_resource_id', sa.String(length=120), nullable=True),
    sa.Column('watch_expiration', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('pk'),
    sa.UniqueConstraint('tenant_id', 'provider', 'calendar_ref')
    )
    op.create_index(op.f('ix_m11_calendar_sources_id'), 'm11_calendar_sources', ['id'], unique=False)
    op.create_index(op.f('ix_m11_calendar_sources_tenant_id'), 'm11_calendar_sources', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_m11_calendar_sources_watch_channel_id'), 'm11_calendar_sources', ['watch_channel_id'], unique=False)
    op.create_table('m11_planned_blocks',
    sa.Column('pk', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('plan_id', sa.String(length=36), nullable=False),
    sa.Column('task_id', sa.String(length=36), nullable=False),
    sa.Column('kind', sa.String(length=10), nullable=False),
    sa.Column('start', sa.DateTime(timezone=True), nullable=False),
    sa.Column('end', sa.DateTime(timezone=True), nullable=False),
    sa.Column('location', sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint('pk')
    )
    op.create_index(op.f('ix_m11_planned_blocks_plan_id'), 'm11_planned_blocks', ['plan_id'], unique=False)
    op.create_index(op.f('ix_m11_planned_blocks_tenant_id'), 'm11_planned_blocks', ['tenant_id'], unique=False)
    op.create_table('m11_plans',
    sa.Column('pk', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('week_start', sa.String(length=10), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('approval_id', sa.String(length=36), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('pk')
    )
    op.create_index(op.f('ix_m11_plans_id'), 'm11_plans', ['id'], unique=False)
    op.create_index(op.f('ix_m11_plans_tenant_id'), 'm11_plans', ['tenant_id'], unique=False)
    op.create_table('m11_scheduling_prefs',
    sa.Column('pk', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('prefs', sa.JSON(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('pk'),
    sa.UniqueConstraint('tenant_id')
    )
    op.create_table('m11_scheduling_tasks',
    sa.Column('pk', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('title', sa.Text(), nullable=False),
    sa.Column('duration_minutes', sa.Integer(), nullable=False),
    sa.Column('deadline', sa.DateTime(timezone=True), nullable=False),
    sa.Column('priority', sa.Integer(), nullable=False),
    sa.Column('location', sa.Text(), nullable=True),
    sa.Column('prep_minutes', sa.Integer(), nullable=False),
    sa.Column('splittable', sa.Boolean(), nullable=False),
    sa.Column('min_block_minutes', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('pk')
    )
    op.create_index(op.f('ix_m11_scheduling_tasks_id'), 'm11_scheduling_tasks', ['id'], unique=False)
    op.create_index(op.f('ix_m11_scheduling_tasks_tenant_id'), 'm11_scheduling_tasks', ['tenant_id'], unique=False)
    op.create_table('m13_application_sessions',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('session_id', sa.String(length=60), nullable=False),
    sa.Column('data', sa.JSON(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant_id', 'session_id')
    )
    op.create_index(op.f('ix_m13_application_sessions_session_id'), 'm13_application_sessions', ['session_id'], unique=False)
    op.create_index(op.f('ix_m13_application_sessions_tenant_id'), 'm13_application_sessions', ['tenant_id'], unique=False)
    op.create_table('m13_browser_audit_events',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('run_id', sa.String(length=120), nullable=False),
    sa.Column('action', sa.String(length=30), nullable=False),
    sa.Column('payload', sa.JSON(), nullable=False),
    sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_m13_browser_audit_events_run_id'), 'm13_browser_audit_events', ['run_id'], unique=False)
    op.create_index(op.f('ix_m13_browser_audit_events_tenant_id'), 'm13_browser_audit_events', ['tenant_id'], unique=False)
    op.create_table('m13_consumed_approvals',
    sa.Column('approval_id', sa.String(length=200), nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('consumed_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('approval_id')
    )
    op.create_index(op.f('ix_m13_consumed_approvals_tenant_id'), 'm13_consumed_approvals', ['tenant_id'], unique=False)
    op.create_table('m14_artifacts',
    sa.Column('pk', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('project_id', sa.String(length=36), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('manifest', sa.JSON(), nullable=False),
    sa.Column('payload', sa.LargeBinary(), nullable=False),
    sa.PrimaryKeyConstraint('pk'),
    sa.UniqueConstraint('tenant_id', 'project_id', 'id')
    )
    op.create_index(op.f('ix_m14_artifacts_project_id'), 'm14_artifacts', ['project_id'], unique=False)
    op.create_index(op.f('ix_m14_artifacts_tenant_id'), 'm14_artifacts', ['tenant_id'], unique=False)
    op.create_table('m14_milestones',
    sa.Column('pk', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('project_id', sa.String(length=36), nullable=False),
    sa.Column('milestone_id', sa.String(length=160), nullable=False),
    sa.Column('data', sa.JSON(), nullable=False),
    sa.PrimaryKeyConstraint('pk'),
    sa.UniqueConstraint('tenant_id', 'project_id', 'milestone_id')
    )
    op.create_index(op.f('ix_m14_milestones_project_id'), 'm14_milestones', ['project_id'], unique=False)
    op.create_index(op.f('ix_m14_milestones_tenant_id'), 'm14_milestones', ['tenant_id'], unique=False)
    op.create_table('m14_projects',
    sa.Column('pk', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('goal', sa.Text(), nullable=False),
    sa.Column('brief', sa.JSON(), nullable=False),
    sa.Column('budget', sa.JSON(), nullable=False),
    sa.Column('status', sa.String(length=40), nullable=False),
    sa.Column('revision', sa.Integer(), nullable=False),
    sa.Column('plan', sa.JSON(), nullable=True),
    sa.PrimaryKeyConstraint('pk'),
    sa.UniqueConstraint('tenant_id', 'id')
    )
    op.create_index(op.f('ix_m14_projects_id'), 'm14_projects', ['id'], unique=False)
    op.create_index(op.f('ix_m14_projects_status'), 'm14_projects', ['status'], unique=False)
    op.create_index(op.f('ix_m14_projects_tenant_id'), 'm14_projects', ['tenant_id'], unique=False)
    op.create_table('m15_document_versions',
    sa.Column('pk', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('document_id', sa.String(length=120), nullable=False),
    sa.Column('version_number', sa.Integer(), nullable=False),
    sa.Column('format', sa.String(length=20), nullable=False),
    sa.Column('template_id', sa.String(length=200), nullable=False),
    sa.Column('content', sa.JSON(), nullable=False),
    sa.Column('parent_version_id', sa.String(length=36), nullable=True),
    sa.Column('content_hash', sa.String(length=64), nullable=False),
    sa.Column('status', sa.String(length=40), nullable=False),
    sa.Column('output_uri', sa.Text(), nullable=True),
    sa.Column('citations', sa.JSON(), nullable=False),
    sa.Column('figures', sa.JSON(), nullable=False),
    sa.PrimaryKeyConstraint('pk'),
    sa.UniqueConstraint('tenant_id', 'document_id', 'version_number'),
    sa.UniqueConstraint('tenant_id', 'id')
    )
    op.create_index(op.f('ix_m15_document_versions_content_hash'), 'm15_document_versions', ['content_hash'], unique=False)
    op.create_index(op.f('ix_m15_document_versions_document_id'), 'm15_document_versions', ['document_id'], unique=False)
    op.create_index(op.f('ix_m15_document_versions_id'), 'm15_document_versions', ['id'], unique=False)
    op.create_index(op.f('ix_m15_document_versions_status'), 'm15_document_versions', ['status'], unique=False)
    op.create_index(op.f('ix_m15_document_versions_tenant_id'), 'm15_document_versions', ['tenant_id'], unique=False)
    op.create_table('m16_agent_status',
    sa.Column('pk', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('module_id', sa.Integer(), nullable=False),
    sa.Column('agent_id', sa.String(length=120), nullable=False),
    sa.Column('state', sa.String(length=20), nullable=False),
    sa.Column('current_task', sa.String(length=500), nullable=True),
    sa.Column('detail', sa.JSON(), nullable=False),
    sa.Column('last_heartbeat', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('pk'),
    sa.UniqueConstraint('tenant_id', 'agent_id', name='uq_m16_agent')
    )
    op.create_index(op.f('ix_m16_agent_status_module_id'), 'm16_agent_status', ['module_id'], unique=False)
    op.create_index(op.f('ix_m16_agent_status_tenant_id'), 'm16_agent_status', ['tenant_id'], unique=False)
    op.create_table('m16_alert_rules',
    sa.Column('pk', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('id', sa.String(length=80), nullable=False),
    sa.Column('kpi_id', sa.String(length=80), nullable=False),
    sa.Column('comparator', sa.String(length=8), nullable=False),
    sa.Column('threshold', sa.Float(), nullable=False),
    sa.Column('severity', sa.String(length=20), nullable=False),
    sa.Column('message', sa.String(length=300), nullable=True),
    sa.Column('cooldown_hours', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('pk'),
    sa.UniqueConstraint('tenant_id', 'id', name='uq_m16_alert_rule')
    )
    op.create_index(op.f('ix_m16_alert_rules_tenant_id'), 'm16_alert_rules', ['tenant_id'], unique=False)
    op.create_table('m16_analysis_jobs',
    sa.Column('pk', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('method', sa.String(length=60), nullable=False),
    sa.Column('feature_row', sa.Integer(), nullable=False),
    sa.Column('data', sa.JSON(), nullable=False),
    sa.Column('params', sa.JSON(), nullable=False),
    sa.Column('seed', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('output', sa.JSON(), nullable=True),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('pk'),
    sa.UniqueConstraint('tenant_id', 'id', name='uq_m16_analysis_job')
    )
    op.create_index(op.f('ix_m16_analysis_jobs_method'), 'm16_analysis_jobs', ['method'], unique=False)
    op.create_index(op.f('ix_m16_analysis_jobs_tenant_id'), 'm16_analysis_jobs', ['tenant_id'], unique=False)
    op.create_table('m16_approvals',
    sa.Column('pk', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('module_id', sa.Integer(), nullable=False),
    sa.Column('action_type', sa.String(length=120), nullable=False),
    sa.Column('title', sa.String(length=500), nullable=False),
    sa.Column('summary', sa.Text(), nullable=False),
    sa.Column('risk', sa.String(length=20), nullable=False),
    sa.Column('evidence', sa.JSON(), nullable=False),
    sa.Column('proposed_payload', sa.JSON(), nullable=False),
    sa.Column('state', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('reviewed_by', sa.String(length=120), nullable=True),
    sa.Column('review_note', sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint('pk'),
    sa.UniqueConstraint('tenant_id', 'id', name='uq_m16_approval')
    )
    op.create_index(op.f('ix_m16_approvals_tenant_id'), 'm16_approvals', ['tenant_id'], unique=False)
    op.create_table('m16_ceremonies',
    sa.Column('pk', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('sprint_id', sa.String(length=36), nullable=False),
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('notes', sa.Text(), nullable=False),
    sa.Column('action_items', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('pk'),
    sa.UniqueConstraint('tenant_id', 'id', name='uq_m16_ceremony')
    )
    op.create_index(op.f('ix_m16_ceremonies_sprint_id'), 'm16_ceremonies', ['sprint_id'], unique=False)
    op.create_index(op.f('ix_m16_ceremonies_tenant_id'), 'm16_ceremonies', ['tenant_id'], unique=False)
    op.create_table('m16_commands',
    sa.Column('pk', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('actor_id', sa.String(length=120), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('utterance', sa.Text(), nullable=False),
    sa.Column('intent', sa.String(length=120), nullable=False),
    sa.Column('parameters', sa.JSON(), nullable=False),
    sa.Column('plan', sa.JSON(), nullable=False),
    sa.Column('read_only', sa.Boolean(), nullable=False),
    sa.Column('confidence', sa.Float(), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('executed_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('pk')
    )
    op.create_index(op.f('ix_m16_commands_id'), 'm16_commands', ['id'], unique=False)
    op.create_index(op.f('ix_m16_commands_tenant_id'), 'm16_commands', ['tenant_id'], unique=False)
    op.create_table('m16_events',
    sa.Column('pk', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('sequence', sa.Integer(), nullable=False),
    sa.Column('topic', sa.String(length=120), nullable=False),
    sa.Column('aggregate_type', sa.String(length=80), nullable=False),
    sa.Column('aggregate_id', sa.String(length=200), nullable=False),
    sa.Column('payload', sa.JSON(), nullable=False),
    sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('pk'),
    sa.UniqueConstraint('tenant_id', 'sequence', name='uq_m16_sequence')
    )
    op.create_index(op.f('ix_m16_events_tenant_id'), 'm16_events', ['tenant_id'], unique=False)
    op.create_table('m16_experiments',
    sa.Column('pk', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('hypothesis', sa.Text(), nullable=False),
    sa.Column('metric', sa.String(length=120), nullable=False),
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.Column('variants', sa.JSON(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('pk'),
    sa.UniqueConstraint('tenant_id', 'id', name='uq_m16_experiment')
    )
    op.create_index(op.f('ix_m16_experiments_tenant_id'), 'm16_experiments', ['tenant_id'], unique=False)
    op.create_table('m16_kpi_definitions',
    sa.Column('pk', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('id', sa.String(length=80), nullable=False),
    sa.Column('label', sa.String(length=120), nullable=False),
    sa.Column('unit', sa.String(length=20), nullable=False),
    sa.Column('topics', sa.JSON(), nullable=False),
    sa.Column('window_hours', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('pk'),
    sa.UniqueConstraint('tenant_id', 'id', name='uq_m16_kpi_definition')
    )
    op.create_index(op.f('ix_m16_kpi_definitions_tenant_id'), 'm16_kpi_definitions', ['tenant_id'], unique=False)
    op.create_table('m16_kpi_points',
    sa.Column('pk', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('kpi_id', sa.String(length=80), nullable=False),
    sa.Column('window_hours', sa.Integer(), nullable=False),
    sa.Column('value', sa.Float(), nullable=False),
    sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('pk')
    )
    op.create_index(op.f('ix_m16_kpi_points_recorded_at'), 'm16_kpi_points', ['recorded_at'], unique=False)
    op.create_index(op.f('ix_m16_kpi_points_tenant_id'), 'm16_kpi_points', ['tenant_id'], unique=False)
    op.create_table('m16_retrospectives',
    sa.Column('pk', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('sprint_id', sa.String(length=36), nullable=False),
    sa.Column('went_well', sa.JSON(), nullable=False),
    sa.Column('didnt_go_well', sa.JSON(), nullable=False),
    sa.Column('action_items', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('pk'),
    sa.UniqueConstraint('tenant_id', 'id', name='uq_m16_retro')
    )
    op.create_index(op.f('ix_m16_retrospectives_sprint_id'), 'm16_retrospectives', ['sprint_id'], unique=False)
    op.create_index(op.f('ix_m16_retrospectives_tenant_id'), 'm16_retrospectives', ['tenant_id'], unique=False)
    op.create_table('m16_roadmaps',
    sa.Column('pk', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('horizon_start', sa.DateTime(timezone=True), nullable=False),
    sa.Column('horizon_end', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('pk'),
    sa.UniqueConstraint('tenant_id', 'id', name='uq_m16_roadmap')
    )
    op.create_index(op.f('ix_m16_roadmaps_tenant_id'), 'm16_roadmaps', ['tenant_id'], unique=False)
    op.create_table('m16_snapshots',
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('last_sequence', sa.Integer(), nullable=False),
    sa.Column('data', sa.JSON(), nullable=False),
    sa.Column('generated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('tenant_id')
    )
    op.create_table('m16_sprints',
    sa.Column('pk', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('goal', sa.Text(), nullable=False),
    sa.Column('start', sa.DateTime(timezone=True), nullable=False),
    sa.Column('end', sa.DateTime(timezone=True), nullable=False),
    sa.Column('capacity_points', sa.Float(), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('pk'),
    sa.UniqueConstraint('tenant_id', 'id', name='uq_m16_sprint')
    )
    op.create_index(op.f('ix_m16_sprints_tenant_id'), 'm16_sprints', ['tenant_id'], unique=False)
    op.create_table('m16_view_prefs',
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('layout', sa.JSON(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('tenant_id')
    )
    op.create_table('m16_work_items',
    sa.Column('pk', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('title', sa.String(length=300), nullable=False),
    sa.Column('item_type', sa.String(length=40), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('estimate', sa.Float(), nullable=True),
    sa.Column('reach', sa.Float(), nullable=True),
    sa.Column('impact', sa.Float(), nullable=True),
    sa.Column('confidence', sa.Float(), nullable=True),
    sa.Column('effort', sa.Float(), nullable=True),
    sa.Column('value', sa.Float(), nullable=True),
    sa.Column('rank', sa.Integer(), nullable=False),
    sa.Column('sprint_id', sa.String(length=36), nullable=True),
    sa.Column('roadmap_id', sa.String(length=36), nullable=True),
    sa.Column('planned_start', sa.DateTime(timezone=True), nullable=True),
    sa.Column('planned_end', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('pk'),
    sa.UniqueConstraint('tenant_id', 'id', name='uq_m16_work_item')
    )
    op.create_index(op.f('ix_m16_work_items_roadmap_id'), 'm16_work_items', ['roadmap_id'], unique=False)
    op.create_index(op.f('ix_m16_work_items_sprint_id'), 'm16_work_items', ['sprint_id'], unique=False)
    op.create_index(op.f('ix_m16_work_items_status'), 'm16_work_items', ['status'], unique=False)
    op.create_index(op.f('ix_m16_work_items_tenant_id'), 'm16_work_items', ['tenant_id'], unique=False)
    op.create_table('m19_decisions',
    sa.Column('pk', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('idea_id', sa.String(length=36), nullable=False),
    sa.Column('from_stage', sa.String(length=30), nullable=False),
    sa.Column('to_stage', sa.String(length=30), nullable=False),
    sa.Column('rationale', sa.Text(), nullable=False),
    sa.Column('actor_id', sa.String(length=120), nullable=False),
    sa.Column('metadata_json', sa.JSON(), nullable=False),
    sa.Column('decided_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('idea_version', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('pk'),
    sa.UniqueConstraint('id')
    )
    op.create_index(op.f('ix_m19_decisions_idea_id'), 'm19_decisions', ['idea_id'], unique=False)
    op.create_index(op.f('ix_m19_decisions_tenant_id'), 'm19_decisions', ['tenant_id'], unique=False)
    op.create_table('m19_evidence',
    sa.Column('pk', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('idea_id', sa.String(length=36), nullable=False),
    sa.Column('kind', sa.String(length=30), nullable=False),
    sa.Column('claim', sa.Text(), nullable=False),
    sa.Column('source', sa.Text(), nullable=False),
    sa.Column('polarity', sa.String(length=20), nullable=False),
    sa.Column('strength', sa.Float(), nullable=False),
    sa.Column('confidence', sa.Float(), nullable=False),
    sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('metadata_json', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('pk')
    )
    op.create_index(op.f('ix_m19_evidence_id'), 'm19_evidence', ['id'], unique=True)
    op.create_index(op.f('ix_m19_evidence_idea_id'), 'm19_evidence', ['idea_id'], unique=False)
    op.create_index(op.f('ix_m19_evidence_tenant_id'), 'm19_evidence', ['tenant_id'], unique=False)
    op.create_table('m19_experiments',
    sa.Column('pk', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('idea_id', sa.String(length=36), nullable=False),
    sa.Column('payload', sa.JSON(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('observed_value', sa.Float(), nullable=True),
    sa.Column('learnings', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('pk'),
    sa.UniqueConstraint('id')
    )
    op.create_index(op.f('ix_m19_experiments_idea_id'), 'm19_experiments', ['idea_id'], unique=False)
    op.create_index(op.f('ix_m19_experiments_tenant_id'), 'm19_experiments', ['tenant_id'], unique=False)
    op.create_table('m19_feasibility_tests',
    sa.Column('pk', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('idea_id', sa.String(length=36), nullable=False),
    sa.Column('payload', sa.JSON(), nullable=False),
    sa.Column('weighted_score', sa.Float(), nullable=False),
    sa.Column('weighted_confidence', sa.Float(), nullable=False),
    sa.Column('outcome', sa.String(length=20), nullable=False),
    sa.Column('tested_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('pk'),
    sa.UniqueConstraint('id')
    )
    op.create_index(op.f('ix_m19_feasibility_tests_idea_id'), 'm19_feasibility_tests', ['idea_id'], unique=False)
    op.create_index(op.f('ix_m19_feasibility_tests_tenant_id'), 'm19_feasibility_tests', ['tenant_id'], unique=False)
    op.create_table('m19_ideas',
    sa.Column('pk', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('title', sa.String(length=180), nullable=False),
    sa.Column('problem', sa.Text(), nullable=False),
    sa.Column('proposed_solution', sa.Text(), nullable=False),
    sa.Column('tags', sa.JSON(), nullable=False),
    sa.Column('metadata_json', sa.JSON(), nullable=False),
    sa.Column('stage', sa.String(length=30), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('pk')
    )
    op.create_index(op.f('ix_m19_ideas_id'), 'm19_ideas', ['id'], unique=True)
    op.create_index(op.f('ix_m19_ideas_stage'), 'm19_ideas', ['stage'], unique=False)
    op.create_index(op.f('ix_m19_ideas_tenant_id'), 'm19_ideas', ['tenant_id'], unique=False)
    op.create_table('m21_corrections',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('actor_id', sa.String(length=120), nullable=False),
    sa.Column('original', sa.Text(), nullable=False),
    sa.Column('correction', sa.Text(), nullable=False),
    sa.Column('context', sa.Text(), nullable=False),
    sa.Column('embedding', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_m21_corrections_actor_id'), 'm21_corrections', ['actor_id'], unique=False)
    op.create_index(op.f('ix_m21_corrections_tenant_id'), 'm21_corrections', ['tenant_id'], unique=False)
    op.create_table('m21_decision_outcomes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('actor_id', sa.String(length=120), nullable=False),
    sa.Column('decision_id', sa.Integer(), nullable=False),
    sa.Column('outcome', sa.Text(), nullable=False),
    sa.Column('rating', sa.String(length=20), nullable=False),
    sa.Column('lesson', sa.Text(), nullable=False),
    sa.Column('evidence', sa.JSON(), nullable=False),
    sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_m21_decision_outcomes_actor_id'), 'm21_decision_outcomes', ['actor_id'], unique=False)
    op.create_index(op.f('ix_m21_decision_outcomes_decision_id'), 'm21_decision_outcomes', ['decision_id'], unique=False)
    op.create_index(op.f('ix_m21_decision_outcomes_tenant_id'), 'm21_decision_outcomes', ['tenant_id'], unique=False)
    op.create_table('m21_decisions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('actor_id', sa.String(length=120), nullable=False),
    sa.Column('decision', sa.Text(), nullable=False),
    sa.Column('reason', sa.Text(), nullable=False),
    sa.Column('context', sa.Text(), nullable=False),
    sa.Column('embedding', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_m21_decisions_actor_id'), 'm21_decisions', ['actor_id'], unique=False)
    op.create_index(op.f('ix_m21_decisions_tenant_id'), 'm21_decisions', ['tenant_id'], unique=False)
    op.create_table('m21_rankings',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('actor_id', sa.String(length=120), nullable=False),
    sa.Column('context', sa.Text(), nullable=False),
    sa.Column('options', sa.JSON(), nullable=False),
    sa.Column('ranking', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_m21_rankings_actor_id'), 'm21_rankings', ['actor_id'], unique=False)
    op.create_index(op.f('ix_m21_rankings_tenant_id'), 'm21_rankings', ['tenant_id'], unique=False)
    op.create_table('m21_reasoning_notes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('actor_id', sa.String(length=120), nullable=False),
    sa.Column('title', sa.Text(), nullable=False),
    sa.Column('owner_authored_note', sa.Text(), nullable=False),
    sa.Column('embedding', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_m21_reasoning_notes_actor_id'), 'm21_reasoning_notes', ['actor_id'], unique=False)
    op.create_index(op.f('ix_m21_reasoning_notes_tenant_id'), 'm21_reasoning_notes', ['tenant_id'], unique=False)
    op.create_table('m21_telemetry_consent',
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('enabled', sa.Boolean(), nullable=False),
    sa.Column('scopes', sa.JSON(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('tenant_id')
    )
    op.create_table('m21_telemetry_events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('actor_id', sa.String(length=120), nullable=False),
    sa.Column('kind', sa.String(length=80), nullable=False),
    sa.Column('payload', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_m21_telemetry_events_actor_id'), 'm21_telemetry_events', ['actor_id'], unique=False)
    op.create_index(op.f('ix_m21_telemetry_events_tenant_id'), 'm21_telemetry_events', ['tenant_id'], unique=False)
    op.create_table('m21_weekly_reviews',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('actor_id', sa.String(length=120), nullable=False),
    sa.Column('artifact_id', sa.String(length=200), nullable=False),
    sa.Column('rating', sa.String(length=20), nullable=False),
    sa.Column('note', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_m21_weekly_reviews_actor_id'), 'm21_weekly_reviews', ['actor_id'], unique=False)
    op.create_index(op.f('ix_m21_weekly_reviews_tenant_id'), 'm21_weekly_reviews', ['tenant_id'], unique=False)
    op.create_table('m23_advising_results',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('kind', sa.String(length=40), nullable=False),
    sa.Column('inputs', sa.JSON(), nullable=False),
    sa.Column('result', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_m23_advising_results_kind'), 'm23_advising_results', ['kind'], unique=False)
    op.create_index(op.f('ix_m23_advising_results_tenant_id'), 'm23_advising_results', ['tenant_id'], unique=False)
    op.create_table('m23_brandids',
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('values', sa.JSON(), nullable=False),
    sa.Column('patterns', sa.JSON(), nullable=False),
    sa.Column('strengths', sa.JSON(), nullable=False),
    sa.Column('evidence', sa.JSON(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('tenant_id')
    )
    op.create_table('m23_identity_interview_turns',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('session_id', sa.String(length=36), nullable=False),
    sa.Column('ordinal', sa.Integer(), nullable=False),
    sa.Column('modality', sa.String(length=10), nullable=False),
    sa.Column('question', sa.Text(), nullable=False),
    sa.Column('student_response', sa.Text(), nullable=False),
    sa.Column('evidence_tags', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_m23_identity_interview_turns_session_id'), 'm23_identity_interview_turns', ['session_id'], unique=False)
    op.create_table('m23_identity_interviews',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('track', sa.String(length=20), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('question_index', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_m23_identity_interviews_tenant_id'), 'm23_identity_interviews', ['tenant_id'], unique=False)
    op.create_table('m23_story_projects',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('title', sa.String(length=500), nullable=False),
    sa.Column('track', sa.String(length=20), nullable=False),
    sa.Column('opportunity', sa.JSON(), nullable=False),
    sa.Column('status', sa.String(length=30), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_m23_story_projects_tenant_id'), 'm23_story_projects', ['tenant_id'], unique=False)
    op.create_table('m23_story_versions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('project_id', sa.Integer(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('student_text', sa.Text(), nullable=False),
    sa.Column('coach_feedback', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('project_id', 'version')
    )
    op.create_index(op.f('ix_m23_story_versions_project_id'), 'm23_story_versions', ['project_id'], unique=False)
    op.create_table('m24_billing_events',
    sa.Column('id', sa.String(length=120), nullable=False),
    sa.Column('type', sa.String(length=120), nullable=False),
    sa.Column('payload', sa.JSON(), nullable=False),
    sa.Column('processed_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('m24_billing_executions',
    sa.Column('approval_id', sa.String(length=36), nullable=False),
    sa.Column('result', sa.JSON(), nullable=False),
    sa.Column('executed_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('approval_id')
    )
    op.create_table('m24_invoices',
    sa.Column('id', sa.String(length=200), nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('status', sa.String(length=40), nullable=False),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('amount_due', sa.Integer(), nullable=False),
    sa.Column('amount_paid', sa.Integer(), nullable=False),
    sa.Column('period_start', sa.DateTime(timezone=True), nullable=True),
    sa.Column('period_end', sa.DateTime(timezone=True), nullable=True),
    sa.Column('hosted_invoice_url', sa.String(length=2000), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_m24_invoices_tenant_id'), 'm24_invoices', ['tenant_id'], unique=False)
    op.create_table('m24_tenant_billing',
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('plan_id', sa.String(length=40), nullable=False),
    sa.Column('status', sa.String(length=30), nullable=False),
    sa.Column('customer_id', sa.String(length=200), nullable=True),
    sa.Column('subscription_id', sa.String(length=200), nullable=True),
    sa.Column('current_period_start', sa.DateTime(timezone=True), nullable=True),
    sa.Column('current_period_end', sa.DateTime(timezone=True), nullable=True),
    sa.Column('cancel_at_period_end', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('tenant_id')
    )
    op.create_index(op.f('ix_m24_tenant_billing_customer_id'), 'm24_tenant_billing', ['customer_id'], unique=False)
    op.create_index(op.f('ix_m24_tenant_billing_subscription_id'), 'm24_tenant_billing', ['subscription_id'], unique=False)
    op.create_table('m24_usage',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('metric', sa.String(length=80), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('idempotency_key', sa.String(length=160), nullable=False),
    sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('event_metadata', sa.JSON(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant_id', 'idempotency_key', name='uq_m24_usage_tenant_key')
    )
    op.create_index(op.f('ix_m24_usage_metric'), 'm24_usage', ['metric'], unique=False)
    op.create_index(op.f('ix_m24_usage_occurred_at'), 'm24_usage', ['occurred_at'], unique=False)
    op.create_index(op.f('ix_m24_usage_tenant_id'), 'm24_usage', ['tenant_id'], unique=False)
    op.create_table('market_factor_values',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('observation_id', sa.BigInteger(), nullable=False),
    sa.Column('factor_key', sa.String(length=500), nullable=False),
    sa.Column('value', sa.Float(), nullable=False),
    sa.Column('unit', sa.String(length=80), nullable=True),
    sa.Column('provenance', sa.JSON(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant_id', 'observation_id', 'factor_key')
    )
    op.create_index(op.f('ix_market_factor_values_factor_key'), 'market_factor_values', ['factor_key'], unique=False)
    op.create_index(op.f('ix_market_factor_values_observation_id'), 'market_factor_values', ['observation_id'], unique=False)
    op.create_index(op.f('ix_market_factor_values_tenant_id'), 'market_factor_values', ['tenant_id'], unique=False)
    op.create_table('market_observations',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('source', sa.String(length=80), nullable=False),
    sa.Column('external_id', sa.String(length=300), nullable=False),
    sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('payload', sa.JSON(), nullable=False),
    sa.Column('source_url', sa.Text(), nullable=False),
    sa.Column('collected_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('source', 'external_id', 'observed_at')
    )
    op.create_index(op.f('ix_market_observations_external_id'), 'market_observations', ['external_id'], unique=False)
    op.create_index(op.f('ix_market_observations_observed_at'), 'market_observations', ['observed_at'], unique=False)
    op.create_index(op.f('ix_market_observations_source'), 'market_observations', ['source'], unique=False)
    op.create_index(op.f('ix_market_observations_tenant_id'), 'market_observations', ['tenant_id'], unique=False)
    op.create_table('memory_embeddings',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('namespace', sa.String(length=120), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('metadata_json', sa.JSON(), nullable=False),
    sa.Column('embedding', Vector(1024), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_memory_embeddings_namespace'), 'memory_embeddings', ['namespace'], unique=False)
    op.create_index(op.f('ix_memory_embeddings_tenant_id'), 'memory_embeddings', ['tenant_id'], unique=False)
    op.create_table('outcome_evidence',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('opportunity_id', sa.String(length=200), nullable=False),
    sa.Column('source_type', sa.String(length=40), nullable=False),
    sa.Column('source_url', sa.Text(), nullable=False),
    sa.Column('source_record_id', sa.String(length=300), nullable=True),
    sa.Column('features', sa.JSON(), nullable=False),
    sa.Column('won', sa.Boolean(), nullable=True),
    sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_outcome_evidence_opportunity_id'), 'outcome_evidence', ['opportunity_id'], unique=False)
    op.create_index(op.f('ix_outcome_evidence_tenant_id'), 'outcome_evidence', ['tenant_id'], unique=False)
    op.create_table('prediction_provenance',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('tenant_id', sa.String(length=120), nullable=False),
    sa.Column('opportunity_id', sa.String(length=200), nullable=False),
    sa.Column('model_version', sa.String(length=100), nullable=False),
    sa.Column('evidence_ids', sa.JSON(), nullable=False),
    sa.Column('explanation', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_prediction_provenance_opportunity_id'), 'prediction_provenance', ['opportunity_id'], unique=False)
    op.create_index(op.f('ix_prediction_provenance_tenant_id'), 'prediction_provenance', ['tenant_id'], unique=False)
    op.drop_index(op.f('ix_m20_skills_name'), table_name='m20_skills')
    op.drop_index(op.f('ix_m20_skills_tenant_id'), table_name='m20_skills')
    op.drop_table('m20_skills')
    op.drop_index(op.f('ix_m20_episodes_task_id'), table_name='m20_episodes')
    op.drop_index(op.f('ix_m20_episodes_tenant_id'), table_name='m20_episodes')
    op.drop_table('m20_episodes')
    op.drop_index(op.f('ix_m20_working_chunks_partition'), table_name='m20_working_chunks')
    op.drop_index(op.f('ix_m20_working_chunks_tenant_id'), table_name='m20_working_chunks')
    op.drop_table('m20_working_chunks')
    op.drop_index(op.f('ix_m20_retrospectives_task_id'), table_name='m20_retrospectives')
    op.drop_index(op.f('ix_m20_retrospectives_tenant_id'), table_name='m20_retrospectives')
    op.drop_table('m20_retrospectives')
    op.drop_index(op.f('ix_m20_traces_task_id'), table_name='m20_traces')
    op.drop_index(op.f('ix_m20_traces_tenant_id'), table_name='m20_traces')
    op.drop_table('m20_traces')
    op.drop_index(op.f('ix_m20_tasks_tenant_id'), table_name='m20_tasks')
    op.drop_table('m20_tasks')
    op.drop_index(op.f('ix_m20_htn_methods_name'), table_name='m20_htn_methods')
    op.drop_index(op.f('ix_m20_htn_methods_status'), table_name='m20_htn_methods')
    op.drop_index(op.f('ix_m20_htn_methods_tenant_id'), table_name='m20_htn_methods')
    op.drop_table('m20_htn_methods')
    op.drop_index(op.f('ix_m20_semantic_facts_tenant_id'), table_name='m20_semantic_facts')
    op.drop_table('m20_semantic_facts')
    op.drop_index(op.f('ix_m20_calibration_claims_resolved'), table_name='m20_calibration_claims')
    op.drop_index(op.f('ix_m20_calibration_claims_tenant_id'), table_name='m20_calibration_claims')
    op.drop_table('m20_calibration_claims')
    op.drop_index(op.f('ix_m20_knowledge_edges_from_id'), table_name='m20_knowledge_edges')
    op.drop_index(op.f('ix_m20_knowledge_edges_tenant_id'), table_name='m20_knowledge_edges')
    op.drop_index(op.f('ix_m20_knowledge_edges_to_id'), table_name='m20_knowledge_edges')
    op.drop_table('m20_knowledge_edges')
def downgrade():
    # Destructive rollback is explicit and intentionally leaves the shared vector extension installed.
    op.create_table('m20_knowledge_edges',
    sa.Column('id', sa.VARCHAR(), nullable=False),
    sa.Column('tenant_id', sa.VARCHAR(), nullable=False),
    sa.Column('from_id', sa.VARCHAR(), nullable=False),
    sa.Column('to_id', sa.VARCHAR(), nullable=False),
    sa.Column('relation', sa.VARCHAR(), nullable=False),
    sa.Column('metadata_json', sa.JSON(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_m20_knowledge_edges_to_id'), 'm20_knowledge_edges', ['to_id'], unique=False)
    op.create_index(op.f('ix_m20_knowledge_edges_tenant_id'), 'm20_knowledge_edges', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_m20_knowledge_edges_from_id'), 'm20_knowledge_edges', ['from_id'], unique=False)
    op.create_table('m20_calibration_claims',
    sa.Column('id', sa.VARCHAR(), nullable=False),
    sa.Column('tenant_id', sa.VARCHAR(), nullable=False),
    sa.Column('payload_json', sa.JSON(), nullable=False),
    sa.Column('resolved', sa.BOOLEAN(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_m20_calibration_claims_tenant_id'), 'm20_calibration_claims', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_m20_calibration_claims_resolved'), 'm20_calibration_claims', ['resolved'], unique=False)
    op.create_table('m20_semantic_facts',
    sa.Column('id', sa.VARCHAR(), nullable=False),
    sa.Column('tenant_id', sa.VARCHAR(), nullable=False),
    sa.Column('content', sa.TEXT(), nullable=False),
    sa.Column('kind', sa.VARCHAR(), nullable=False),
    sa.Column('confidence', sa.FLOAT(), nullable=False),
    sa.Column('decay_rate', sa.FLOAT(), nullable=False),
    sa.Column('provenance_json', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DATETIME(), nullable=False),
    sa.Column('last_confirmed_at', sa.DATETIME(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_m20_semantic_facts_tenant_id'), 'm20_semantic_facts', ['tenant_id'], unique=False)
    op.create_table('m20_htn_methods',
    sa.Column('id', sa.VARCHAR(), nullable=False),
    sa.Column('tenant_id', sa.VARCHAR(), nullable=False),
    sa.Column('name', sa.VARCHAR(), nullable=False),
    sa.Column('status', sa.VARCHAR(), nullable=False),
    sa.Column('payload_json', sa.JSON(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_m20_htn_methods_tenant_id'), 'm20_htn_methods', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_m20_htn_methods_status'), 'm20_htn_methods', ['status'], unique=False)
    op.create_index(op.f('ix_m20_htn_methods_name'), 'm20_htn_methods', ['name'], unique=False)
    op.create_table('m20_tasks',
    sa.Column('id', sa.VARCHAR(), nullable=False),
    sa.Column('tenant_id', sa.VARCHAR(), nullable=False),
    sa.Column('goal', sa.TEXT(), nullable=False),
    sa.Column('state', sa.VARCHAR(), nullable=False),
    sa.Column('importance', sa.INTEGER(), nullable=False),
    sa.Column('deadline', sa.DATETIME(), nullable=True),
    sa.Column('plan_json', sa.JSON(), nullable=False),
    sa.Column('standup_notes_json', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DATETIME(), nullable=False),
    sa.Column('updated_at', sa.DATETIME(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_m20_tasks_tenant_id'), 'm20_tasks', ['tenant_id'], unique=False)
    op.create_table('m20_traces',
    sa.Column('id', sa.VARCHAR(), nullable=False),
    sa.Column('tenant_id', sa.VARCHAR(), nullable=False),
    sa.Column('task_id', sa.VARCHAR(), nullable=True),
    sa.Column('phase', sa.VARCHAR(), nullable=False),
    sa.Column('detail', sa.TEXT(), nullable=False),
    sa.Column('policy_basis', sa.VARCHAR(), nullable=False),
    sa.Column('created_at', sa.DATETIME(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_m20_traces_tenant_id'), 'm20_traces', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_m20_traces_task_id'), 'm20_traces', ['task_id'], unique=False)
    op.create_table('m20_retrospectives',
    sa.Column('id', sa.VARCHAR(), nullable=False),
    sa.Column('tenant_id', sa.VARCHAR(), nullable=False),
    sa.Column('task_id', sa.VARCHAR(), nullable=False),
    sa.Column('payload_json', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DATETIME(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_m20_retrospectives_tenant_id'), 'm20_retrospectives', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_m20_retrospectives_task_id'), 'm20_retrospectives', ['task_id'], unique=False)
    op.create_table('m20_working_chunks',
    sa.Column('id', sa.VARCHAR(), nullable=False),
    sa.Column('tenant_id', sa.VARCHAR(), nullable=False),
    sa.Column('partition', sa.VARCHAR(), nullable=False),
    sa.Column('payload_json', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DATETIME(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_m20_working_chunks_tenant_id'), 'm20_working_chunks', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_m20_working_chunks_partition'), 'm20_working_chunks', ['partition'], unique=False)
    op.create_table('m20_episodes',
    sa.Column('id', sa.VARCHAR(), nullable=False),
    sa.Column('tenant_id', sa.VARCHAR(), nullable=False),
    sa.Column('task_id', sa.VARCHAR(), nullable=False),
    sa.Column('goal', sa.TEXT(), nullable=False),
    sa.Column('outcome', sa.VARCHAR(), nullable=False),
    sa.Column('payload_json', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DATETIME(), nullable=False),
    sa.ForeignKeyConstraint(['task_id'], ['m20_tasks.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_m20_episodes_tenant_id'), 'm20_episodes', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_m20_episodes_task_id'), 'm20_episodes', ['task_id'], unique=False)
    op.create_table('m20_skills',
    sa.Column('id', sa.VARCHAR(), nullable=False),
    sa.Column('tenant_id', sa.VARCHAR(), nullable=False),
    sa.Column('name', sa.VARCHAR(), nullable=False),
    sa.Column('version', sa.INTEGER(), nullable=False),
    sa.Column('status', sa.VARCHAR(), nullable=False),
    sa.Column('payload_json', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DATETIME(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_m20_skills_tenant_id'), 'm20_skills', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_m20_skills_name'), 'm20_skills', ['name'], unique=False)
    op.drop_index(op.f('ix_prediction_provenance_tenant_id'), table_name='prediction_provenance')
    op.drop_index(op.f('ix_prediction_provenance_opportunity_id'), table_name='prediction_provenance')
    op.drop_table('prediction_provenance')
    op.drop_index(op.f('ix_outcome_evidence_tenant_id'), table_name='outcome_evidence')
    op.drop_index(op.f('ix_outcome_evidence_opportunity_id'), table_name='outcome_evidence')
    op.drop_table('outcome_evidence')
    op.drop_index(op.f('ix_memory_embeddings_tenant_id'), table_name='memory_embeddings')
    op.drop_index(op.f('ix_memory_embeddings_namespace'), table_name='memory_embeddings')
    op.drop_table('memory_embeddings')
    op.drop_index(op.f('ix_market_observations_tenant_id'), table_name='market_observations')
    op.drop_index(op.f('ix_market_observations_source'), table_name='market_observations')
    op.drop_index(op.f('ix_market_observations_observed_at'), table_name='market_observations')
    op.drop_index(op.f('ix_market_observations_external_id'), table_name='market_observations')
    op.drop_table('market_observations')
    op.drop_index(op.f('ix_market_factor_values_tenant_id'), table_name='market_factor_values')
    op.drop_index(op.f('ix_market_factor_values_observation_id'), table_name='market_factor_values')
    op.drop_index(op.f('ix_market_factor_values_factor_key'), table_name='market_factor_values')
    op.drop_table('market_factor_values')
    op.drop_index(op.f('ix_m24_usage_tenant_id'), table_name='m24_usage')
    op.drop_index(op.f('ix_m24_usage_occurred_at'), table_name='m24_usage')
    op.drop_index(op.f('ix_m24_usage_metric'), table_name='m24_usage')
    op.drop_table('m24_usage')
    op.drop_index(op.f('ix_m24_tenant_billing_subscription_id'), table_name='m24_tenant_billing')
    op.drop_index(op.f('ix_m24_tenant_billing_customer_id'), table_name='m24_tenant_billing')
    op.drop_table('m24_tenant_billing')
    op.drop_index(op.f('ix_m24_invoices_tenant_id'), table_name='m24_invoices')
    op.drop_table('m24_invoices')
    op.drop_table('m24_billing_executions')
    op.drop_table('m24_billing_events')
    op.drop_index(op.f('ix_m23_story_versions_project_id'), table_name='m23_story_versions')
    op.drop_table('m23_story_versions')
    op.drop_index(op.f('ix_m23_story_projects_tenant_id'), table_name='m23_story_projects')
    op.drop_table('m23_story_projects')
    op.drop_index(op.f('ix_m23_identity_interviews_tenant_id'), table_name='m23_identity_interviews')
    op.drop_table('m23_identity_interviews')
    op.drop_index(op.f('ix_m23_identity_interview_turns_session_id'), table_name='m23_identity_interview_turns')
    op.drop_table('m23_identity_interview_turns')
    op.drop_table('m23_brandids')
    op.drop_index(op.f('ix_m23_advising_results_tenant_id'), table_name='m23_advising_results')
    op.drop_index(op.f('ix_m23_advising_results_kind'), table_name='m23_advising_results')
    op.drop_table('m23_advising_results')
    op.drop_index(op.f('ix_m21_weekly_reviews_tenant_id'), table_name='m21_weekly_reviews')
    op.drop_index(op.f('ix_m21_weekly_reviews_actor_id'), table_name='m21_weekly_reviews')
    op.drop_table('m21_weekly_reviews')
    op.drop_index(op.f('ix_m21_telemetry_events_tenant_id'), table_name='m21_telemetry_events')
    op.drop_index(op.f('ix_m21_telemetry_events_actor_id'), table_name='m21_telemetry_events')
    op.drop_table('m21_telemetry_events')
    op.drop_table('m21_telemetry_consent')
    op.drop_index(op.f('ix_m21_reasoning_notes_tenant_id'), table_name='m21_reasoning_notes')
    op.drop_index(op.f('ix_m21_reasoning_notes_actor_id'), table_name='m21_reasoning_notes')
    op.drop_table('m21_reasoning_notes')
    op.drop_index(op.f('ix_m21_rankings_tenant_id'), table_name='m21_rankings')
    op.drop_index(op.f('ix_m21_rankings_actor_id'), table_name='m21_rankings')
    op.drop_table('m21_rankings')
    op.drop_index(op.f('ix_m21_decisions_tenant_id'), table_name='m21_decisions')
    op.drop_index(op.f('ix_m21_decisions_actor_id'), table_name='m21_decisions')
    op.drop_table('m21_decisions')
    op.drop_index(op.f('ix_m21_decision_outcomes_tenant_id'), table_name='m21_decision_outcomes')
    op.drop_index(op.f('ix_m21_decision_outcomes_decision_id'), table_name='m21_decision_outcomes')
    op.drop_index(op.f('ix_m21_decision_outcomes_actor_id'), table_name='m21_decision_outcomes')
    op.drop_table('m21_decision_outcomes')
    op.drop_index(op.f('ix_m21_corrections_tenant_id'), table_name='m21_corrections')
    op.drop_index(op.f('ix_m21_corrections_actor_id'), table_name='m21_corrections')
    op.drop_table('m21_corrections')
    op.drop_index(op.f('ix_m19_ideas_tenant_id'), table_name='m19_ideas')
    op.drop_index(op.f('ix_m19_ideas_stage'), table_name='m19_ideas')
    op.drop_index(op.f('ix_m19_ideas_id'), table_name='m19_ideas')
    op.drop_table('m19_ideas')
    op.drop_index(op.f('ix_m19_feasibility_tests_tenant_id'), table_name='m19_feasibility_tests')
    op.drop_index(op.f('ix_m19_feasibility_tests_idea_id'), table_name='m19_feasibility_tests')
    op.drop_table('m19_feasibility_tests')
    op.drop_index(op.f('ix_m19_experiments_tenant_id'), table_name='m19_experiments')
    op.drop_index(op.f('ix_m19_experiments_idea_id'), table_name='m19_experiments')
    op.drop_table('m19_experiments')
    op.drop_index(op.f('ix_m19_evidence_tenant_id'), table_name='m19_evidence')
    op.drop_index(op.f('ix_m19_evidence_idea_id'), table_name='m19_evidence')
    op.drop_index(op.f('ix_m19_evidence_id'), table_name='m19_evidence')
    op.drop_table('m19_evidence')
    op.drop_index(op.f('ix_m19_decisions_tenant_id'), table_name='m19_decisions')
    op.drop_index(op.f('ix_m19_decisions_idea_id'), table_name='m19_decisions')
    op.drop_table('m19_decisions')
    op.drop_index(op.f('ix_m16_work_items_tenant_id'), table_name='m16_work_items')
    op.drop_index(op.f('ix_m16_work_items_status'), table_name='m16_work_items')
    op.drop_index(op.f('ix_m16_work_items_sprint_id'), table_name='m16_work_items')
    op.drop_index(op.f('ix_m16_work_items_roadmap_id'), table_name='m16_work_items')
    op.drop_table('m16_work_items')
    op.drop_table('m16_view_prefs')
    op.drop_index(op.f('ix_m16_sprints_tenant_id'), table_name='m16_sprints')
    op.drop_table('m16_sprints')
    op.drop_table('m16_snapshots')
    op.drop_index(op.f('ix_m16_roadmaps_tenant_id'), table_name='m16_roadmaps')
    op.drop_table('m16_roadmaps')
    op.drop_index(op.f('ix_m16_retrospectives_tenant_id'), table_name='m16_retrospectives')
    op.drop_index(op.f('ix_m16_retrospectives_sprint_id'), table_name='m16_retrospectives')
    op.drop_table('m16_retrospectives')
    op.drop_index(op.f('ix_m16_kpi_points_tenant_id'), table_name='m16_kpi_points')
    op.drop_index(op.f('ix_m16_kpi_points_recorded_at'), table_name='m16_kpi_points')
    op.drop_table('m16_kpi_points')
    op.drop_index(op.f('ix_m16_kpi_definitions_tenant_id'), table_name='m16_kpi_definitions')
    op.drop_table('m16_kpi_definitions')
    op.drop_index(op.f('ix_m16_experiments_tenant_id'), table_name='m16_experiments')
    op.drop_table('m16_experiments')
    op.drop_index(op.f('ix_m16_events_tenant_id'), table_name='m16_events')
    op.drop_table('m16_events')
    op.drop_index(op.f('ix_m16_commands_tenant_id'), table_name='m16_commands')
    op.drop_index(op.f('ix_m16_commands_id'), table_name='m16_commands')
    op.drop_table('m16_commands')
    op.drop_index(op.f('ix_m16_ceremonies_tenant_id'), table_name='m16_ceremonies')
    op.drop_index(op.f('ix_m16_ceremonies_sprint_id'), table_name='m16_ceremonies')
    op.drop_table('m16_ceremonies')
    op.drop_index(op.f('ix_m16_approvals_tenant_id'), table_name='m16_approvals')
    op.drop_table('m16_approvals')
    op.drop_index(op.f('ix_m16_analysis_jobs_tenant_id'), table_name='m16_analysis_jobs')
    op.drop_index(op.f('ix_m16_analysis_jobs_method'), table_name='m16_analysis_jobs')
    op.drop_table('m16_analysis_jobs')
    op.drop_index(op.f('ix_m16_alert_rules_tenant_id'), table_name='m16_alert_rules')
    op.drop_table('m16_alert_rules')
    op.drop_index(op.f('ix_m16_agent_status_tenant_id'), table_name='m16_agent_status')
    op.drop_index(op.f('ix_m16_agent_status_module_id'), table_name='m16_agent_status')
    op.drop_table('m16_agent_status')
    op.drop_index(op.f('ix_m15_document_versions_tenant_id'), table_name='m15_document_versions')
    op.drop_index(op.f('ix_m15_document_versions_status'), table_name='m15_document_versions')
    op.drop_index(op.f('ix_m15_document_versions_id'), table_name='m15_document_versions')
    op.drop_index(op.f('ix_m15_document_versions_document_id'), table_name='m15_document_versions')
    op.drop_index(op.f('ix_m15_document_versions_content_hash'), table_name='m15_document_versions')
    op.drop_table('m15_document_versions')
    op.drop_index(op.f('ix_m14_projects_tenant_id'), table_name='m14_projects')
    op.drop_index(op.f('ix_m14_projects_status'), table_name='m14_projects')
    op.drop_index(op.f('ix_m14_projects_id'), table_name='m14_projects')
    op.drop_table('m14_projects')
    op.drop_index(op.f('ix_m14_milestones_tenant_id'), table_name='m14_milestones')
    op.drop_index(op.f('ix_m14_milestones_project_id'), table_name='m14_milestones')
    op.drop_table('m14_milestones')
    op.drop_index(op.f('ix_m14_artifacts_tenant_id'), table_name='m14_artifacts')
    op.drop_index(op.f('ix_m14_artifacts_project_id'), table_name='m14_artifacts')
    op.drop_table('m14_artifacts')
    op.drop_index(op.f('ix_m13_consumed_approvals_tenant_id'), table_name='m13_consumed_approvals')
    op.drop_table('m13_consumed_approvals')
    op.drop_index(op.f('ix_m13_browser_audit_events_tenant_id'), table_name='m13_browser_audit_events')
    op.drop_index(op.f('ix_m13_browser_audit_events_run_id'), table_name='m13_browser_audit_events')
    op.drop_table('m13_browser_audit_events')
    op.drop_index(op.f('ix_m13_application_sessions_tenant_id'), table_name='m13_application_sessions')
    op.drop_index(op.f('ix_m13_application_sessions_session_id'), table_name='m13_application_sessions')
    op.drop_table('m13_application_sessions')
    op.drop_index(op.f('ix_m11_scheduling_tasks_tenant_id'), table_name='m11_scheduling_tasks')
    op.drop_index(op.f('ix_m11_scheduling_tasks_id'), table_name='m11_scheduling_tasks')
    op.drop_table('m11_scheduling_tasks')
    op.drop_table('m11_scheduling_prefs')
    op.drop_index(op.f('ix_m11_plans_tenant_id'), table_name='m11_plans')
    op.drop_index(op.f('ix_m11_plans_id'), table_name='m11_plans')
    op.drop_table('m11_plans')
    op.drop_index(op.f('ix_m11_planned_blocks_tenant_id'), table_name='m11_planned_blocks')
    op.drop_index(op.f('ix_m11_planned_blocks_plan_id'), table_name='m11_planned_blocks')
    op.drop_table('m11_planned_blocks')
    op.drop_index(op.f('ix_m11_calendar_sources_watch_channel_id'), table_name='m11_calendar_sources')
    op.drop_index(op.f('ix_m11_calendar_sources_tenant_id'), table_name='m11_calendar_sources')
    op.drop_index(op.f('ix_m11_calendar_sources_id'), table_name='m11_calendar_sources')
    op.drop_table('m11_calendar_sources')
    op.drop_index(op.f('ix_m11_calendar_events_log_tenant_id'), table_name='m11_calendar_events_log')
    op.drop_index(op.f('ix_m11_calendar_events_log_entity_id'), table_name='m11_calendar_events_log')
    op.drop_table('m11_calendar_events_log')
    op.drop_index(op.f('ix_m11_calendar_events_tenant_id'), table_name='m11_calendar_events')
    op.drop_index(op.f('ix_m11_calendar_events_source_id'), table_name='m11_calendar_events')
    op.drop_index(op.f('ix_m11_calendar_events_id'), table_name='m11_calendar_events')
    op.drop_table('m11_calendar_events')
    op.drop_index(op.f('ix_m10_gmail_accounts_tenant_id'), table_name='m10_gmail_accounts')
    op.drop_index(op.f('ix_m10_gmail_accounts_id'), table_name='m10_gmail_accounts')
    op.drop_table('m10_gmail_accounts')
    op.drop_index(op.f('ix_m10_email_messages_thread_id'), table_name='m10_email_messages')
    op.drop_index(op.f('ix_m10_email_messages_tenant_id'), table_name='m10_email_messages')
    op.drop_index(op.f('ix_m10_email_messages_sender'), table_name='m10_email_messages')
    op.drop_index(op.f('ix_m10_email_messages_id'), table_name='m10_email_messages')
    op.drop_index(op.f('ix_m10_email_messages_category'), table_name='m10_email_messages')
    op.drop_index(op.f('ix_m10_email_messages_account_id'), table_name='m10_email_messages')
    op.drop_table('m10_email_messages')
    op.drop_index(op.f('ix_m10_email_events_tenant_id'), table_name='m10_email_events')
    op.drop_index(op.f('ix_m10_email_events_entity_id'), table_name='m10_email_events')
    op.drop_table('m10_email_events')
    op.drop_index(op.f('ix_m10_email_drafts_tenant_id'), table_name='m10_email_drafts')
    op.drop_index(op.f('ix_m10_email_drafts_message_id'), table_name='m10_email_drafts')
    op.drop_index(op.f('ix_m10_email_drafts_id'), table_name='m10_email_drafts')
    op.drop_index(op.f('ix_m10_email_drafts_approval_id'), table_name='m10_email_drafts')
    op.drop_table('m10_email_drafts')
    op.drop_index(op.f('ix_m10_action_items_tenant_id'), table_name='m10_action_items')
    op.drop_index(op.f('ix_m10_action_items_message_id'), table_name='m10_action_items')
    op.drop_index(op.f('ix_m10_action_items_id'), table_name='m10_action_items')
    op.drop_table('m10_action_items')
    op.drop_index(op.f('ix_m09_suggestions_tenant_id'), table_name='m09_suggestions')
    op.drop_index(op.f('ix_m09_suggestions_id'), table_name='m09_suggestions')
    op.drop_table('m09_suggestions')
    op.drop_index(op.f('ix_m09_nodes_title'), table_name='m09_nodes')
    op.drop_index(op.f('ix_m09_nodes_tenant_id'), table_name='m09_nodes')
    op.drop_index(op.f('ix_m09_nodes_node_type'), table_name='m09_nodes')
    op.drop_index(op.f('ix_m09_nodes_id'), table_name='m09_nodes')
    op.drop_table('m09_nodes')
    op.drop_index(op.f('ix_m09_edges_tenant_id'), table_name='m09_edges')
    op.drop_index(op.f('ix_m09_edges_target_id'), table_name='m09_edges')
    op.drop_index(op.f('ix_m09_edges_source_id'), table_name='m09_edges')
    op.drop_index(op.f('ix_m09_edges_id'), table_name='m09_edges')
    op.drop_table('m09_edges')
    op.drop_index(op.f('ix_m09_audit_tenant_id'), table_name='m09_audit')
    op.drop_table('m09_audit')
    op.drop_index(op.f('ix_m08_builds_tenant_id'), table_name='m08_builds')
    op.drop_index(op.f('ix_m08_builds_project_id'), table_name='m08_builds')
    op.drop_index(op.f('ix_m08_builds_id'), table_name='m08_builds')
    op.drop_table('m08_builds')
    op.drop_index(op.f('ix_m07_partnership_events_tenant_id'), table_name='m07_partnership_events')
    op.drop_index(op.f('ix_m07_partnership_events_id'), table_name='m07_partnership_events')
    op.drop_index(op.f('ix_m07_partnership_events_brand_id'), table_name='m07_partnership_events')
    op.drop_table('m07_partnership_events')
    op.drop_index(op.f('ix_m07_brands_tenant_id'), table_name='m07_brands')
    op.drop_index(op.f('ix_m07_brands_id'), table_name='m07_brands')
    op.drop_table('m07_brands')
    op.drop_index(op.f('ix_m07_artifacts_tenant_id'), table_name='m07_artifacts')
    op.drop_index(op.f('ix_m07_artifacts_id'), table_name='m07_artifacts')
    op.drop_index(op.f('ix_m07_artifacts_brand_id'), table_name='m07_artifacts')
    op.drop_table('m07_artifacts')
    op.drop_index(op.f('ix_m06_social_snapshots_tenant_id'), table_name='m06_social_snapshots')
    op.drop_index(op.f('ix_m06_social_snapshots_platform'), table_name='m06_social_snapshots')
    op.drop_index(op.f('ix_m06_social_snapshots_item_id'), table_name='m06_social_snapshots')
    op.drop_table('m06_social_snapshots')
    op.drop_index(op.f('ix_m06_social_schedules_tenant_id'), table_name='m06_social_schedules')
    op.drop_index(op.f('ix_m06_social_schedules_status'), table_name='m06_social_schedules')
    op.drop_index(op.f('ix_m06_social_schedules_item_id'), table_name='m06_social_schedules')
    op.drop_table('m06_social_schedules')
    op.drop_index(op.f('ix_m06_social_reports_tenant_id'), table_name='m06_social_reports')
    op.drop_index(op.f('ix_m06_social_reports_item_id'), table_name='m06_social_reports')
    op.drop_table('m06_social_reports')
    op.drop_index(op.f('ix_m06_social_publishes_tenant_id'), table_name='m06_social_publishes')
    op.drop_index(op.f('ix_m06_social_publishes_item_id'), table_name='m06_social_publishes')
    op.drop_table('m06_social_publishes')
    op.drop_index(op.f('ix_m06_social_plans_tenant_id'), table_name='m06_social_plans')
    op.drop_index(op.f('ix_m06_social_plans_item_id'), table_name='m06_social_plans')
    op.drop_table('m06_social_plans')
    op.drop_index(op.f('ix_m06_social_artifacts_tenant_id'), table_name='m06_social_artifacts')
    op.drop_index(op.f('ix_m06_social_artifacts_kind'), table_name='m06_social_artifacts')
    op.drop_index(op.f('ix_m06_social_artifacts_item_id'), table_name='m06_social_artifacts')
    op.drop_table('m06_social_artifacts')
    op.drop_index(op.f('ix_m06_social_ab_tests_tenant_id'), table_name='m06_social_ab_tests')
    op.drop_index(op.f('ix_m06_social_ab_tests_item_id'), table_name='m06_social_ab_tests')
    op.drop_table('m06_social_ab_tests')
    op.drop_index(op.f('ix_m05_messages_tenant_id'), table_name='m05_messages')
    op.drop_index(op.f('ix_m05_messages_status'), table_name='m05_messages')
    op.drop_index(op.f('ix_m05_messages_id'), table_name='m05_messages')
    op.drop_index(op.f('ix_m05_messages_contact_id'), table_name='m05_messages')
    op.drop_index(op.f('ix_m05_messages_campaign_id'), table_name='m05_messages')
    op.drop_table('m05_messages')
    op.drop_index(op.f('ix_m05_message_events_tenant_id'), table_name='m05_message_events')
    op.drop_index(op.f('ix_m05_message_events_message_id'), table_name='m05_message_events')
    op.drop_table('m05_message_events')
    op.drop_index(op.f('ix_m05_contacts_tenant_id'), table_name='m05_contacts')
    op.drop_index(op.f('ix_m05_contacts_project_id'), table_name='m05_contacts')
    op.drop_index(op.f('ix_m05_contacts_id'), table_name='m05_contacts')
    op.drop_index(op.f('ix_m05_contacts_email'), table_name='m05_contacts')
    op.drop_table('m05_contacts')
    op.drop_index(op.f('ix_m05_contact_changes_tenant_id'), table_name='m05_contact_changes')
    op.drop_index(op.f('ix_m05_contact_changes_contact_id'), table_name='m05_contact_changes')
    op.drop_table('m05_contact_changes')
    op.drop_index(op.f('ix_m05_campaigns_tenant_id'), table_name='m05_campaigns')
    op.drop_index(op.f('ix_m05_campaigns_status'), table_name='m05_campaigns')
    op.drop_index(op.f('ix_m05_campaigns_project_id'), table_name='m05_campaigns')
    op.drop_index(op.f('ix_m05_campaigns_id'), table_name='m05_campaigns')
    op.drop_table('m05_campaigns')
    op.drop_index(op.f('ix_m04_surveillance_papers_tenant_id'), table_name='m04_surveillance_papers')
    op.drop_index(op.f('ix_m04_surveillance_papers_paper_id'), table_name='m04_surveillance_papers')
    op.drop_table('m04_surveillance_papers')
    op.drop_index(op.f('ix_m03_funded_awards_tenant_id'), table_name='m03_funded_awards')
    op.drop_index(op.f('ix_m03_funded_awards_source'), table_name='m03_funded_awards')
    op.drop_index(op.f('ix_m03_funded_awards_award_id'), table_name='m03_funded_awards')
    op.drop_table('m03_funded_awards')
    op.drop_index(op.f('ix_m02_profile_documents_tenant_id'), table_name='m02_profile_documents')
    op.drop_table('m02_profile_documents')
    op.drop_table('m02_corpus_onboarding')
    op.drop_index(op.f('ix_m02_competitions_tenant_id'), table_name='m02_competitions')
    op.drop_index(op.f('ix_m02_competitions_competition_id'), table_name='m02_competitions')
    op.drop_table('m02_competitions')
    op.drop_index(op.f('ix_m01_opportunities_url'), table_name='m01_opportunities')
    op.drop_index(op.f('ix_m01_opportunities_source_id'), table_name='m01_opportunities')
    op.drop_index(op.f('ix_m01_opportunities_opportunity_type'), table_name='m01_opportunities')
    op.drop_index(op.f('ix_m01_opportunities_match_score'), table_name='m01_opportunities')
    op.drop_table('m01_opportunities')
    op.drop_index(op.f('ix_m00_approval_requests_user_id'), table_name='m00_approval_requests')
    op.drop_index(op.f('ix_m00_approval_requests_status'), table_name='m00_approval_requests')
    op.drop_index(op.f('ix_m00_approval_requests_action_type'), table_name='m00_approval_requests')
    op.drop_table('m00_approval_requests')
    op.drop_index(op.f('ix_m00_approval_policies_priority'), table_name='m00_approval_policies')
    op.drop_index(op.f('ix_m00_approval_policies_module_id'), table_name='m00_approval_policies')
    op.drop_index(op.f('ix_m00_approval_policies_enabled'), table_name='m00_approval_policies')
    op.drop_table('m00_approval_policies')
    op.drop_index(op.f('ix_m00_approval_idempotency_approval_id'), table_name='m00_approval_idempotency')
    op.drop_table('m00_approval_idempotency')
    op.drop_index(op.f('ix_m00_approval_events_approval_id'), table_name='m00_approval_events')
    op.drop_table('m00_approval_events')
    op.drop_index(op.f('ix_m00_approval_effects_effect_id'), table_name='m00_approval_effects')
    op.drop_index(op.f('ix_m00_approval_effects_approval_id'), table_name='m00_approval_effects')
    op.drop_table('m00_approval_effects')
    op.drop_index(op.f('ix_discovery_candidates_tenant_id'), table_name='discovery_candidates')
    op.drop_index(op.f('ix_discovery_candidates_status'), table_name='discovery_candidates')
    op.drop_index(op.f('ix_discovery_candidates_platform'), table_name='discovery_candidates')
    op.drop_table('discovery_candidates')
    op.drop_index(op.f('ix_collection_sources_tenant_id'), table_name='collection_sources')
    op.drop_index(op.f('ix_collection_sources_priority'), table_name='collection_sources')
    op.drop_index(op.f('ix_collection_sources_next_run_at'), table_name='collection_sources')
    op.drop_index(op.f('ix_collection_sources_collector_type'), table_name='collection_sources')
    op.drop_table('collection_sources')
    op.drop_index(op.f('ix_collection_runs_tenant_id'), table_name='collection_runs')
    op.drop_index(op.f('ix_collection_runs_source_key'), table_name='collection_runs')
    op.drop_table('collection_runs')
    op.drop_index(op.f('ix_collected_records_tenant_id'), table_name='collected_records')
    op.drop_index(op.f('ix_collected_records_source_key'), table_name='collected_records')
    op.drop_index(op.f('ix_collected_records_content_hash'), table_name='collected_records')
    op.drop_table('collected_records')
