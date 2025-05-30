"""Add first_login to User

Revision ID: add_first_login_to_user
Revises: 
Create Date: 2025-05-29 18:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_first_login_to_user'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Add first_login column to users table
    op.add_column('users', sa.Column('first_login', sa.Boolean(), nullable=False, server_default='1'))

def downgrade():
    # Remove first_login column from users table
    op.drop_column('users', 'first_login')
