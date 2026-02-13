"""AgriBalance Flask Application Factory."""
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from config import config

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'


def create_app(config_name='default'):
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    
    # Register blueprints
    from app.routes.main import main_bp
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.land import land_bp
    from app.routes.cultivation import cultivation_bp
    from app.routes.selling import selling_bp
    from app.routes.ecommerce import ecommerce_bp
    from app.routes.community import community_bp
    from app.routes.news import news_bp
    from app.routes.settings import settings_bp
    from app.routes.admin import admin_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
    app.register_blueprint(land_bp, url_prefix='/land')
    app.register_blueprint(cultivation_bp, url_prefix='/cultivation')
    app.register_blueprint(selling_bp, url_prefix='/selling')
    app.register_blueprint(ecommerce_bp, url_prefix='/products')
    app.register_blueprint(community_bp, url_prefix='/community')
    app.register_blueprint(news_bp, url_prefix='/news')
    app.register_blueprint(settings_bp, url_prefix='/settings')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    
    # Register error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        """Handle 404 errors - page not found."""
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        """Handle 500 errors - internal server error."""
        db.session.rollback()  # Rollback any pending database transactions
        return render_template('errors/500.html'), 500
    
    @app.errorhandler(403)
    def forbidden_error(error):
        """Handle 403 errors - forbidden access."""
        return render_template('errors/404.html'), 404  # Use 404 template for now
    
    # Create database tables
    with app.app_context():
        db.create_all()
    
    return app
