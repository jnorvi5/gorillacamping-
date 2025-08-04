import os
import logging
from flask import Flask, jsonify
from flask_cors import CORS
from opencensus.ext.azure.log_exporter import AzureLogHandler

from .config import Config
from .services.storage_service import StorageService
from .services.ai_service import AIService
from .services.product_service import ProductService
from .routes.main import main_bp, init_app as init_main_app
from .routes.api import api_bp, init_app as init_api_app
from .routes.admin import admin_bp, init_app as init_admin_app

def create_app():
    """Create and configure an instance of the Flask application."""
    app = Flask(__name__, static_folder='../static', template_folder='../templates')
    app.config.from_object(Config)

    # Set up logging
    logger = logging.getLogger(__name__)
    connection_string = app.config['APPLICATIONINSIGHTS_CONNECTION_STRING']
    if connection_string:
        logger.addHandler(AzureLogHandler(connection_string=connection_string))
        logger.info("Azure Application Insights configured successfully")
    else:
        logger.warning("No Azure Application Insights connection string found")

    # Configure CORS
    CORS(app, origins=[
        "https://gorillacamping.site",
        "https://www.gorillacamping.site",
        "https://gorillacamping.pages.dev",  # Cloudflare Pages default domain
        "http://localhost:3000",  # For local development
    ], supports_credentials=True)

    # Initialize services
    storage_service = StorageService(app)
    ai_service = AIService(app, storage_service)
    product_service = ProductService()

    # Initialize blueprints with services
    init_main_app(app, storage_service)
    init_api_app(app, storage_service, ai_service, product_service)
    init_admin_app(app, storage_service)

    # Register blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')

    # Error Handlers
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({'error': 'Not found'}), 404

    return app
