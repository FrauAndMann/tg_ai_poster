"""Initial schema capturing current database structure

Revision ID: initial_schema
Revises:
Create Date: 2025-03-16 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create initial database schema."""
    # Posts table
    op.create_table(
        'posts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('topic', sa.String(length=500), nullable=True),
        sa.Column('source', sa.String(length=500), nullable=True),
        sa.Column('source_url', sa.String(length=1000), nullable=True),
        sa.Column('published_at', sa.DateTime(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('character_count', sa.Integer(), nullable=True),
        sa.Column('has_emoji', sa.Boolean(), nullable=True),
        sa.Column('emoji_count', sa.Integer(), nullable=True),
        sa.Column('hashtag_count', sa.Integer(), nullable=True),
        sa.Column('views', sa.Integer(), nullable=True),
        sa.Column('reactions', sa.Integer(), nullable=True),
        sa.Column('shares', sa.Integer(), nullable=True),
        sa.Column('comments', sa.Integer(), nullable=True),
        sa.Column('engagement_score', sa.Float(), nullable=True),
        sa.Column('llm_model', sa.String(length=100), nullable=True),
        sa.Column('generation_attempts', sa.Integer(), nullable=True),
        sa.Column('telegram_message_id', sa.Integer(), nullable=True),
        sa.Column('post_type', sa.String(length=50), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('quality_score', sa.Float(), nullable=True),
        sa.Column('editor_score', sa.Float(), nullable=True),
        sa.Column('verification_score', sa.Float(), nullable=True),
        sa.Column('needs_review', sa.Boolean(), nullable=True),
        sa.Column('post_title', sa.String(length=200), nullable=True),
        sa.Column('post_hook', sa.Text(), nullable=True),
        sa.Column('post_body', sa.Text(), nullable=True),
        sa.Column('post_tldr', sa.String(length=300), nullable=True),
        sa.Column('post_analysis', sa.Text(), nullable=True),
        sa.Column('post_key_facts', sa.Text(), nullable=True),
        sa.Column('post_sources', sa.Text(), nullable=True),
        sa.Column('post_hashtags', sa.Text(), nullable=True),
        sa.Column('media_prompt', sa.Text(), nullable=True),
        sa.Column('source_count', sa.Integer(), nullable=True),
        sa.Column('source_tiers', sa.String(length=100), nullable=True),
        sa.Column('media_url', sa.String(length=1000), nullable=True),
        sa.Column('media_source', sa.String(length=50), nullable=True),
        sa.Column('media_photographer', sa.String(length=200), nullable=True),
        sa.Column('pipeline_version', sa.String(length=50), nullable=True),
        sa.Column('version', sa.Integer(), nullable=True),
        sa.Column('current_version_id', sa.Integer(), nullable=True),
        sa.Column('ab_experiment_id', sa.Integer(), nullable=True),
        sa.Column('ab_variant_id', sa.String(length=10), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_posts_published_at', 'posts', ['published_at'])
    op.create_index('ix_posts_status', 'posts', ['status'])
    op.create_index('ix_posts_engagement_score', 'posts', ['engagement_score'])

    # Post Versions table
    op.create_table(
        'post_versions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('post_id', sa.Integer(), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('post_title', sa.String(length=200), nullable=True),
        sa.Column('post_hook', sa.Text(), nullable=True),
        sa.Column('post_body', sa.Text(), nullable=True),
        sa.Column('post_tldr', sa.String(length=300), nullable=True),
        sa.Column('post_hashtags', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.String(length=50), nullable=True),
        sa.Column('change_reason', sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(['post_id'], ['posts.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_post_versions_post_id', 'post_versions', ['post_id'])
    op.create_index('ix_post_versions_created', 'post_versions', ['created_at'])

    # A/B Experiments table
    op.create_table(
        'ab_experiments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('traffic_split', sa.Float(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('ended_at', sa.DateTime(), nullable=True),
        sa.Column('winner_variant', sa.String(length=10), nullable=True),
        sa.Column('confidence_level', sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    # A/B Variants table
    op.create_table(
        'ab_variants',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('experiment_id', sa.Integer(), nullable=False),
        sa.Column('variant_id', sa.String(length=10), nullable=False),
        sa.Column('post_id', sa.Integer(), nullable=True),
        sa.Column('impressions', sa.Integer(), nullable=True),
        sa.Column('total_engagement', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['experiment_id'], ['ab_experiments.id'], ),
        sa.ForeignKeyConstraint(['post_id'], ['posts.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('experiment_id', 'variant_id', name='uq_experiment_variant'),
    )
    op.create_index('ix_ab_variants_experiment', 'ab_variants', ['experiment_id'])

    # Topics table
    op.create_table(
        'topics',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('last_used', sa.DateTime(), nullable=True),
        sa.Column('use_count', sa.Integer(), nullable=True),
        sa.Column('embedding_vector', sa.Text(), nullable=True),
        sa.Column('avg_engagement', sa.Float(), nullable=True),
        sa.Column('success_rate', sa.Float(), nullable=True),
        sa.Column('source_type', sa.String(length=50), nullable=True),
        sa.Column('source_url', sa.String(length=1000), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )
    op.create_index('ix_topics_name', 'topics', ['name'])
    op.create_index('ix_topics_last_used', 'topics', ['last_used'])
    op.create_index('ix_topics_use_count', 'topics', ['use_count'])

    # Sources table
    op.create_table(
        'sources',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('url', sa.String(length=1000), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=True),
        sa.Column('type', sa.String(length=50), nullable=True),
        sa.Column('last_fetched', sa.DateTime(), nullable=True),
        sa.Column('fetch_count', sa.Integer(), nullable=True),
        sa.Column('item_count', sa.Integer(), nullable=True),
        sa.Column('new_items_count', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('consecutive_errors', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('url'),
    )
    op.create_index('ix_sources_url', 'sources', ['url'])
    op.create_index('ix_sources_type', 'sources', ['type'])
    op.create_index('ix_sources_is_active', 'sources', ['is_active'])

    # Style Profiles table
    op.create_table(
        'style_profiles',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('avg_sentence_length', sa.Float(), nullable=True),
        sa.Column('avg_paragraph_count', sa.Float(), nullable=True),
        sa.Column('common_phrases', sa.Text(), nullable=True),
        sa.Column('vocabulary_richness', sa.Float(), nullable=True),
        sa.Column('emoji_patterns', sa.Text(), nullable=True),
        sa.Column('hashtag_patterns', sa.Text(), nullable=True),
        sa.Column('formality_score', sa.Float(), nullable=True),
        sa.Column('enthusiasm_score', sa.Float(), nullable=True),
        sa.Column('technicality_score', sa.Float(), nullable=True),
        sa.Column('posts_analyzed', sa.Integer(), nullable=True),
        sa.Column('last_updated', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    """Remove all tables."""
    op.drop_table('style_profiles')
    op.drop_table('sources')
    op.drop_table('topics')
    op.drop_table('ab_variants')
    op.drop_table('ab_experiments')
    op.drop_table('post_versions')
    op.drop_table('posts')
