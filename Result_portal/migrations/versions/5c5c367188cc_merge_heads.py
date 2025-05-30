"""merge heads

Revision ID: 5c5c367188cc
Revises: 059b4a62f47a, add_first_login_column, add_first_login_to_user
Create Date: 2025-05-29 22:13:52.691037

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5c5c367188cc'
down_revision = ('059b4a62f47a', 'add_first_login_column', 'add_first_login_to_user')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
