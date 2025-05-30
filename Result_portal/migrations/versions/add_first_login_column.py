"""Add first_login to User

Revision ID: add_first_login_column
Revises: 
Create Date: 2025-05-29 18:36:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'add_first_login_column'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Add first_login column to users table with default True
    op.add_column('users', 
        sa.Column('first_login', 
                 mysql.TINYINT(display_width=1), 
                 server_default='1', 
                 nullable=False)
    )

def downgrade():
    # Remove first_login column from users table
    op.drop_column('users', 'first_login')
