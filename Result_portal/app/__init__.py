import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bootstrap import Bootstrap
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from flask_mail import Mail
from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
bootstrap = Bootstrap()
migrate = Migrate()
csrf = CSRFProtect()
mail = Mail()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)
    bootstrap.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    mail.init_app(app)
    
    # Configure logging - always log regardless of debug mode
    if not os.path.exists('logs'):
        try:
            os.mkdir('logs')
        except OSError as e:
            print(f"Error creating logs directory: {e}")
    
    # Clear any existing handlers
    for handler in app.logger.handlers[:]:
        app.logger.removeHandler(handler)
    
    # Set up file handler
    file_handler = RotatingFileHandler('logs/student_portal.log',
                                     maxBytes=10240, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
    file_handler.setLevel(logging.DEBUG if app.debug else logging.INFO)
    
    # Add console handler for debugging
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s'))
    console_handler.setLevel(logging.DEBUG if app.debug else logging.INFO)
    
    # Add both handlers
    app.logger.addHandler(file_handler)
    app.logger.addHandler(console_handler)
    app.logger.setLevel(logging.DEBUG if app.debug else logging.INFO)
    app.logger.info('Student Portal startup')
    app.logger.debug('Debug logging is enabled')
    
    # Add time_ago filter
    @app.template_filter('time_ago')
    def time_ago_filter(value):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        diff = now - value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
        
        periods = (
            (diff.days // 365, 'year', 'years'),
            (diff.days // 30, 'month', 'months'),
            (diff.days // 7, 'week', 'weeks'),
            (diff.days, 'day', 'days'),
            (diff.seconds // 3600, 'hour', 'hours'),
            (diff.seconds // 60, 'minute', 'minutes'),
            (diff.seconds, 'second', 'seconds'),
        )
        
        for period, singular, plural in periods:
            if period >= 1:
                return f'{period} {singular if period == 1 else plural} ago'
        return 'just now'

    # Register blueprints
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')
    
    from app.admin import bp as admin_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')
    
    # Import and initialize student blueprint
    from app.student import bp as student_bp, init_app as init_student
    app.register_blueprint(student_bp, url_prefix='/student')
    # Initialize any extensions or additional setup
    init_student(app)

    # If you have a main blueprint, register it here
    # from app.main import bp as main_bp
    # app.register_blueprint(main_bp)

    @app.route("/")
    def index():
        return render_template('index.html')
    @app.context_processor
    def inject_now():
        from datetime import datetime
        return {'now': datetime.now()}

    return app

from app import models
