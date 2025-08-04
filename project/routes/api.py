from flask import Blueprint, jsonify, request, session, make_response
from ..services.storage_service import StorageService
from ..services.ai_service import AIService
from ..services.product_service import ProductService
from ..utils import generate_visitor_id
import requests

api_bp = Blueprint('api', __name__)

# Note: services will be initialized in the app factory
storage_service = None
ai_service = None
product_service = None

def init_app(app, ss, ais, ps):
    global storage_service, ai_service, product_service
    storage_service = ss
    ai_service = ais
    product_service = ps

@api_bp.route('/blog-posts', methods=['GET'])
def api_blog_posts():
    """Return all blog posts as JSON"""
    posts = storage_service.get_blog_posts()
    return jsonify(posts)

@api_bp.route('/blog-post/<slug>', methods=['GET'])
def api_blog_post(slug):
    """Return a single post by slug"""
    post = storage_service.get_blog_post_by_slug(slug)
    if post:
        return jsonify(post)
    else:
        return jsonify({'error': 'Post not found'}), 404

@api_bp.route('/gear', methods=['GET'])
def api_gear():
    """Return gear items as JSON"""
    gear_items = product_service.get_gear()
    return jsonify(gear_items)

@api_bp.route('/guerilla-chat', methods=['POST'])
def guerilla_chat():
    """AI chatbot endpoint with conversation memory"""
    data = request.get_json()
    user_message = data.get('message', '')
    visitor_id = request.cookies.get('visitor_id', generate_visitor_id())

    # Get conversation history from session
    conversation_history = session.get('conversation', [])

    # Add user message to history
    conversation_history.append({'role': 'user', 'content': user_message})

    # Get AI response
    ai_response = ai_service.guerilla_ai_response(user_message, conversation_history)

    # Add AI response to history
    conversation_history.append({'role': 'assistant', 'content': ai_response})

    # Save conversation to session (limit to last 10 messages)
    session['conversation'] = conversation_history[-10:]

    # Get product recommendations
    product_recommendations = product_service.enhance_response_with_products(user_message, ai_response)

    # Create response
    response = jsonify({
        'response': ai_response,
        'recommendations': product_recommendations,
        'success': True,
        'visitor_id': visitor_id
    })

    # Set visitor ID cookie if not already set
    if not request.cookies.get('visitor_id'):
        response.set_cookie('visitor_id', visitor_id, max_age=60*60*24*365)

    return response

@api_bp.route('/affiliate-click', methods=['POST'])
def affiliate_click():
    """Track affiliate clicks"""
    data = request.get_json()
    product_id = data.get('product_id')
    source = data.get('source', 'api')

    # Track the click
    storage_service.track_affiliate_click(product_id, source)

    return jsonify({'success': True})

@api_bp.route('/subscribe', methods=['POST'])
def subscribe():
    """Add email to subscribers"""
    data = request.get_json()
    email = data.get('email')
    source = data.get('source', 'general')

    if not email or '@' not in email:
        return jsonify({'success': False, 'error': 'Invalid email'}), 400

    success, message = storage_service.add_subscriber(email, source)

    if success:
        # Optional: Integration with MailerLite or other email service
        mailerlite_api_key = request.blueprint.app.config.get('MAILERLITE_API_KEY')
        if mailerlite_api_key:
            try:
                requests.post(
                    'https://api.mailerlite.com/api/v2/subscribers',
                    json={'email': email, 'groups': ['Welcome']},
                    headers={'X-MailerLite-ApiKey': mailerlite_api_key}
                )
            except Exception as e:
                request.blueprint.app.logger.error(f"MailerLite error: {str(e)}")

    if success:
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': message})
