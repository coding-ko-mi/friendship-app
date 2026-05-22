"""Начальная схема: все 11 таблиц MVP.

Создаёт пользователей, интересы, компании, мэтчинг, заявки/голосование
и достижения со всеми связями и ограничениями.

Revision ID: 357e7b0dc368
Revises:
Create Date: 2026-05-21
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# Идентификаторы ревизии, используемые Alembic.
revision: str = '357e7b0dc368'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Создание таблиц. Порядок учитывает зависимости внешних ключей.
    op.create_table('achievements',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('code', sa.String(length=32), nullable=False),
    sa.Column('name', sa.String(length=64), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('code')
    )
    op.create_table('groups',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=False),
    sa.Column('telegram_chat_id', sa.BigInteger(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('telegram_chat_id')
    )
    op.create_table('interests',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=64), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('telegram_id', sa.BigInteger(), nullable=False),
    sa.Column('name', sa.String(length=64), nullable=False),
    sa.Column('age', sa.Integer(), nullable=False),
    sa.Column('about', sa.Text(), nullable=False),
    sa.Column('photo_file_id', sa.String(length=256), nullable=False),
    sa.Column('city', sa.String(length=64), nullable=False),
    sa.Column('is_banned', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('age >= 18 AND age <= 100', name='ck_user_age_range'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_city'), 'users', ['city'], unique=False)
    op.create_index(op.f('ix_users_telegram_id'), 'users', ['telegram_id'], unique=True)
    op.create_table('group_members',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('group_id', sa.Integer(), nullable=False),
    sa.Column('joined_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['group_id'], ['groups.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', 'group_id')
    )
    op.create_table('likes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('from_user_id', sa.Integer(), nullable=False),
    sa.Column('to_user_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('from_user_id <> to_user_id', name='ck_like_not_self'),
    sa.ForeignKeyConstraint(['from_user_id'], ['users.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['to_user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('from_user_id', 'to_user_id', name='uq_like_pair')
    )
    op.create_index(op.f('ix_likes_from_user_id'), 'likes', ['from_user_id'], unique=False)
    op.create_index(op.f('ix_likes_to_user_id'), 'likes', ['to_user_id'], unique=False)
    op.create_table('matches',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_a_id', sa.Integer(), nullable=False),
    sa.Column('user_b_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('user_a_id < user_b_id', name='ck_match_canonical_order'),
    sa.ForeignKeyConstraint(['user_a_id'], ['users.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_b_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_a_id', 'user_b_id', name='uq_match_pair')
    )
    op.create_index(op.f('ix_matches_user_a_id'), 'matches', ['user_a_id'], unique=False)
    op.create_index(op.f('ix_matches_user_b_id'), 'matches', ['user_b_id'], unique=False)
    op.create_table('membership_requests',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('type', sa.Enum('JOIN', 'INVITE', 'MERGE', name='requesttype', native_enum=False, length=16), nullable=False),
    sa.Column('status', sa.Enum('PENDING', 'VOTING', 'ACCEPTED', 'REJECTED', name='requeststatus', native_enum=False, length=16), server_default='pending', nullable=False),
    sa.Column('subject_user_id', sa.Integer(), nullable=True),
    sa.Column('subject_group_id', sa.Integer(), nullable=True),
    sa.Column('target_group_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('(CASE WHEN subject_user_id IS NULL THEN 0 ELSE 1 END) + (CASE WHEN subject_group_id IS NULL THEN 0 ELSE 1 END) = 1', name='ck_request_exactly_one_subject'),
    sa.ForeignKeyConstraint(['subject_group_id'], ['groups.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['subject_user_id'], ['users.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['target_group_id'], ['groups.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_membership_requests_subject_group_id'), 'membership_requests', ['subject_group_id'], unique=False)
    op.create_index(op.f('ix_membership_requests_subject_user_id'), 'membership_requests', ['subject_user_id'], unique=False)
    op.create_index(op.f('ix_membership_requests_target_group_id'), 'membership_requests', ['target_group_id'], unique=False)
    op.create_table('user_achievements',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('achievement_id', sa.Integer(), nullable=False),
    sa.Column('earned_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['achievement_id'], ['achievements.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', 'achievement_id')
    )
    op.create_table('user_interests',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('interest_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['interest_id'], ['interests.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', 'interest_id')
    )
    op.create_table('votes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('request_id', sa.Integer(), nullable=False),
    sa.Column('voter_id', sa.Integer(), nullable=False),
    sa.Column('value', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['request_id'], ['membership_requests.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['voter_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('request_id', 'voter_id', name='uq_vote_once_per_request')
    )
    op.create_index(op.f('ix_votes_request_id'), 'votes', ['request_id'], unique=False)
    op.create_index(op.f('ix_votes_voter_id'), 'votes', ['voter_id'], unique=False)



def downgrade() -> None:
    # Создание таблиц. Порядок учитывает зависимости внешних ключей.
    op.drop_index(op.f('ix_votes_voter_id'), table_name='votes')
    op.drop_index(op.f('ix_votes_request_id'), table_name='votes')
    op.drop_table('votes')
    op.drop_table('user_interests')
    op.drop_table('user_achievements')
    op.drop_index(op.f('ix_membership_requests_target_group_id'), table_name='membership_requests')
    op.drop_index(op.f('ix_membership_requests_subject_user_id'), table_name='membership_requests')
    op.drop_index(op.f('ix_membership_requests_subject_group_id'), table_name='membership_requests')
    op.drop_table('membership_requests')
    op.drop_index(op.f('ix_matches_user_b_id'), table_name='matches')
    op.drop_index(op.f('ix_matches_user_a_id'), table_name='matches')
    op.drop_table('matches')
    op.drop_index(op.f('ix_likes_to_user_id'), table_name='likes')
    op.drop_index(op.f('ix_likes_from_user_id'), table_name='likes')
    op.drop_table('likes')
    op.drop_table('group_members')
    op.drop_index(op.f('ix_users_telegram_id'), table_name='users')
    op.drop_index(op.f('ix_users_city'), table_name='users')
    op.drop_table('users')
    op.drop_table('interests')
    op.drop_table('groups')
    op.drop_table('achievements')

