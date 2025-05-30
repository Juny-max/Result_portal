from flask import Blueprint

# Create the blueprint
bp = Blueprint('student', __name__)

# Import routes after creating the blueprint to avoid circular imports
from . import routes  # noqa: F401

def init_app(app):
    # No need to register the blueprint here as it's already registered in create_app
    pass
