from flask import Blueprint, jsonify, request, current_app
from ..services.storage_service import StorageService

admin_bp = Blueprint('admin', __name__)

# Note: storage_service will be initialized in the app factory
storage_service = None

def init_app(app, ss):
    global storage_service
    storage_service = ss

@admin_bp.route('/api/analytics/summary')
def api_analytics_summary():
    """Return basic analytics for the dashboard"""
    # Simple authentication
    api_key = request.args.get('api_key')
    if api_key != current_app.config['ADMIN_API_KEY']:
        return jsonify({'error': 'Unauthorized'}), 401

    summary = storage_service.get_analytics_summary()
    return jsonify(summary)
