import os
import uuid
import json
import random
import time
from datetime import datetime
from flask import Flask, render_template, jsonify, request, redirect, url_for, session, make_response
from flask_cors import CORS
import requests
import logging
import openai
from azure.identity import DefaultAzureCredential
from azure.ai.inference import ChatCompletionsClient

# --- FLASK SETUP ---
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'gorilla-secret-2025')
CORS(app, supports_credentials=True)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- AZURE AI SETUP ---
openai.api_type = "azure"
openai.azure_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
openai.api_key = os.environ.get("AZURE_OPENAI_KEY") 
openai.api_version = "2024-02-01"

# --- MONGODB SETUP (if available) ---
mongodb_uri = os.environ.get('MONGODB_URI')
if mongodb_uri:
    from pymongo import MongoClient
    client = MongoClient(mongodb_uri)
    db = client.get_default_database()
else:
    # Fallback to in-memory storage for development
    db = {
        'posts': [],
        'subscribers': [],
        'affiliate_clicks': [],
        'ai_usage': [],
        'conversations': {}
    }

# --- GUERILLA AI PERSONALITY ---
GUERILLA_SYSTEM_PROMPT = """
You are Guerilla the Gorilla, a battle-hardened Army veteran turned off-grid camping expert.

PERSONALITY:
- Rough around the edges but genuinely helpful
- Speaks in short, direct sentences
- Uses military/survival terminology
- Budget-conscious and practical
- Slight rebellious streak (hence "guerilla" not "gorilla")
- Motto: "Sometimes life is hard, but you just camp through it"

KNOWLEDGE BASE:
- Extensive camping and survival expertise
- Gear recommendations focused on durability and value
- Off-grid living strategies
- Making money while camping (affiliate marketing, content creation)
- Military survival techniques adapted for civilian camping

PRODUCT RECOMMENDATIONS:
When users ask about gear, recommend from our affiliate products:
- Power: Jackery Explorer 240 ($199.99) - "Powers my laptop for days, paid for itself"
- Water: LifeStraw Filter ($14.96) - "Saved my ass more times than I can count"
- Food: 4Patriots Kit ($197) - "25-year shelf life, actually tastes decent"
- Shelter: REI Co-op Base Camp 4 ($399) - "Bomb-proof tent, worth every penny"
- Cooking: MSR WhisperLite ($119.99) - "Works in any weather, reliable as hell"

TONE: Helpful but blunt. No fluff. Real-world experience. Always end with actionable advice.
"""

# --- HELPER FUNCTIONS ---
def generate_visitor_id():
    return str(uuid.uuid4())

def track_ai_usage(prompt_tokens, completion_tokens, user_id=None, visitor_id=None):
    """Track AI usage for cost monitoring"""
    usage_data = {
        'prompt_tokens': prompt_tokens,
        'completion_tokens': completion_tokens,
        'user_id': user_id,
        'visitor_id': visitor_id,
        'timestamp': datetime.utcnow(),
        'estimated_cost': (prompt_tokens * 0.00001) + (completion_tokens * 0.00003)
    }
    
    if isinstance(db, dict):
        db['ai_usage'].append(usage_data)
    else:
        db.ai_usage.insert_one(usage_data)

def guerilla_ai_response(message, conversation_history=None):
    """Generate AI response with Guerilla personality using Azure OpenAI"""
    if not conversation_history:
        conversation_history = []
    
    try:
        # Use Azure OpenAI
        messages = [{"role": "system", "content": GUERILLA_SYSTEM_PROMPT}]
        
        # Add conversation history (last 10 messages)
        if conversation_history:
            messages.extend(conversation_history[-10:])
            
        messages.append({"role": "user", "content": message})
        
        response = openai.ChatCompletion.create(
            engine=os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o"),
            messages=messages,
            max_tokens=300,
            temperature=0.7
        )
        
        ai_response = response.choices[0].message.content.strip()
        
        # Track usage
        track_ai_usage(
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            visitor_id=request.cookies.get('visitor_id')
        )
        
        return ai_response
        
    except Exception as e:
        logger.error(f"Azure AI error: {str(e)}")
        # Fallback responses
        fallback_responses = [
            "Yo! That's a solid question. From my experience living off-grid, best solution is keep it simple. Need power? Get Jackery 240. Not fancy, but works every time.",
            "Listen up. Been there, done that. Most folks overthink this. For water filtration, LifeStraw saved my ass more times than I can count. $15, lasts forever, no batteries.",
            "Straight talk? Food storage matters most. 4Patriots 72-hour kit fits under bed, tastes decent, lasts 25 years. Start there, build up slowly.",
            "Look, camping's not complicated. Need three things: shelter, water, food. Everything else is luxury. Start with good tarp, water filter, fire starter.",
            "Here's real deal - most expensive gear often breaks first. Buy mid-range, test hard, replace what fails. Jackery's solid for power though, worth every penny."
        ]
        return random.choice(fallback_responses)

# --- FLASK ROUTES ---
@app.route('/')
def home():
    response = make_response(render_template('index.html'))
    if not request.cookies.get('visitor_id'):
        response.set_cookie('visitor_id', generate_visitor_id(), max_age=365*24*60*60)
    return response

@app.route('/blog')
def blog():
    return render_template('blog.html')

@app.route('/blog/<slug>')
def blog_post(slug):
    return render_template('post.html')

@app.route('/gear')
def gear():
    return render_template('gear.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

# --- API ENDPOINTS ---
@app.route('/api/guerilla-chat', methods=['POST'])
def guerilla_chat():
    """Enhanced AI chatbot endpoint with conversation memory"""
    data = request.get_json()
    user_message = data.get('message', '')
    visitor_id = request.cookies.get('visitor_id', generate_visitor_id())
    
    # Get conversation history from session
    conversation_history = session.get('conversation', [])
    
    # Add user message to history
    conversation_history.append({'role': 'user', 'content': user_message})
    
    # Get AI response
    ai_response = guerilla_ai_response(user_message, conversation_history)
    
    # Add AI response to history
    conversation_history.append({'role': 'assistant', 'content': ai_response})
    
    # Save conversation to session (limit to last 10 messages)
    session['conversation'] = conversation_history[-10:]
    
    # Detect product mentions and recommend products
    product_recommendations = []
    keywords = {
        'power': {
            'id': 'jackery-explorer-240',
            'name': 'Jackery Explorer 240',
            'price': '$199.99',
            'image': 'https://static.gorillacamping.site/img/products/jackery.jpg'
        },
        'battery': {
            'id': 'jackery-explorer-240',
            'name': 'Jackery Explorer 240',
            'price': '$199.99',
            'image': 'https://static.gorillacamping.site/img/products/jackery.jpg'
        },
        'water': {
            'id': 'lifestraw-filter',
            'name': 'LifeStraw Water Filter',
            'price': '$14.96',
            'image': 'https://static.gorillacamping.site/img/products/lifestraw.jpg'
        },
        'food': {
            'id': '4patriots-food',
            'name': '4Patriots 72-Hour Kit',
            'price': '$197.00',
            'image': 'https://static.gorillacamping.site/img/products/4patriots.jpg'
        },
        'tent': {
            'id': 'rei-base-camp',
            'name': 'REI Co-op Base Camp 4',
            'price': '$399.00',
            'image': 'https://static.gorillacamping.site/img/products/rei-tent.jpg'
        }
    }
    
    user_message_lower = user_message.lower()
    for keyword, product in keywords.items():
        if keyword in user_message_lower:
            product_recommendations.append(product)
            break
    
    return jsonify({
        'response': ai_response,
        'recommendations': product_recommendations,
        'success': True,
        'visitor_id': visitor_id
    })

@app.route('/api/blog-posts', methods=['GET'])
def api_blog_posts():
    """Return all blog posts as JSON"""
    if isinstance(db, dict):
        posts = [
            {
                "title": "Essential Camping Gear for Guerilla Campers",
                "slug": "essential-camping-gear",
                "created_at": "2025-07-01",
                "excerpt": "The bare minimum you need to survive and thrive in the wilderness without breaking the bank."
            },
            {
                "title": "Guerilla Camping 101: Off-Grid Freedom",
                "slug": "guerilla-camping-101", 
                "created_at": "2025-07-05",
                "excerpt": "How to disappear into nature while staying connected enough to make money online."
            },
            {
                "title": "Power Solutions for Digital Nomads",
                "slug": "power-solutions-digital-nomads",
                "created_at": "2025-07-10",
                "excerpt": "Keep your devices charged and your income flowing while completely off the grid."
            }
        ]
    else:
        posts = list(db.posts.find({"status": "published"}))
        for post in posts:
            post['_id'] = str(post['_id'])
            post['created_at'] = post['created_at'].strftime('%Y-%m-%d')
    
    return jsonify(posts)

@app.route('/api/gear', methods=['GET'])
def api_gear():
    """Return gear items as JSON with affiliate links"""
    gear_items = [
        {
            'name': 'Jackery Explorer 240',
            'image': 'https://static.gorillacamping.site/img/products/jackery.jpg',
            'description': 'Perfect for keeping devices charged off-grid. Powers laptop, phone, lights for days. Paid for itself with just 2 viral videos I made from camp.',
            'affiliate_id': 'jackery-explorer-240',
            'price': '$199.99',
            'old_price': '$299.99',
            'savings': 'Save $100',
            'rating': 5,
            'commission': '8%',
            'badges': ['HOT DEAL', 'BEST VALUE', 'GUERILLA APPROVED']
        },
        {
            'name': 'LifeStraw Personal Water Filter',
            'image': 'https://static.gorillacamping.site/img/products/lifestraw.jpg',
            'description': 'Essential survival gear. Filters 99.999999% of bacteria, parasites. Saved my ass more times than I can count.',
            'affiliate_id': 'lifestraw-filter',
            'price': '$14.96',
            'old_price': '$19.95',
            'savings': 'Save 25%',
            'rating': 5,
            'commission': '12%',
            'badges': ['BESTSELLER', 'EMERGENCY ESSENTIAL']
        },
        {
            'name': '4Patriots 72-Hour Survival Food Kit',
            'image': 'https://static.gorillacamping.site/img/products/4patriots.jpg',
            'description': 'Actual food that doesn\'t taste like cardboard. 25-year shelf life, compact storage.',
            'affiliate_id': '4patriots-food',
            'price': '$197.00',
            'old_price': '$297.00',
            'savings': 'Save $100',
            'rating': 4,
            'commission': '25%',
            'badges': ['HIGH COMMISSION', 'BEGINNER ESSENTIAL']
        },
        {
            'name': 'REI Co-op Base Camp 4 Tent',
            'image': 'https://static.gorillacamping.site/img/products/rei-tent.jpg',
            'description': 'Bomb-proof tent that handles anything nature throws at it. Worth every penny.',
            'affiliate_id': 'rei-base-camp',
            'price': '$399.00',
            'old_price': '$499.00',
            'savings': 'Save $100',
            'rating': 5,
            'commission': '5%',
            'badges': ['DURABILITY KING', 'WEATHER PROOF']
        }
    ]
    return jsonify(gear_items)

@app.route('/api/subscribe', methods=['POST'])
def subscribe():
    """Add email to subscribers with MailerLite integration"""
    data = request.get_json()
    email = data.get('email')
    source = data.get('source', 'general')
    
    if not email or '@' not in email:
        return jsonify({'success': False, 'error': 'Invalid email'}), 400
    
    # Check for existing subscriber
    existing = False
    if isinstance(db, dict):
        for sub in db['subscribers']:
            if sub.get('email') == email:
                existing = True
                break
        
        if not existing:
            db['subscribers'].append({
                'email': email,
                'source': source,
                'timestamp': datetime.utcnow(),
                'visitor_id': request.cookies.get('visitor_id', generate_visitor_id()),
                'active': True
            })
    else:
        existing = db.subscribers.find_one({'email': email})
        if not existing:
            db.subscribers.insert_one({
                'email': email,
                'source': source,
                'timestamp': datetime.utcnow(),
                'visitor_id': request.cookies.get('visitor_id', generate_visitor_id()),
                'active': True
            })
    
    if existing:
        return jsonify({'success': False, 'error': 'Already subscribed'})
    
    # MailerLite integration
    mailerlite_api_key = os.environ.get('MAILERLITE_API_KEY')
    if mailerlite_api_key:
        try:
            requests.post(
                'https://api.mailerlite.com/api/v2/subscribers',
                json={'email': email, 'groups': ['Guerilla Campers']},
                headers={'X-MailerLite-ApiKey': mailerlite_api_key}
            )
        except Exception as e:
            logger.error(f"MailerLite error: {str(e)}")
    
    return jsonify({'success': True})

@app.route('/affiliate/<product>')
def affiliate(product):
    """Track and redirect affiliate clicks"""
    affiliate_links = {
        'jackery-explorer-240': 'https://amzn.to/jackery240',
        'lifestraw-filter': 'https://amzn.to/lifestraw',
        '4patriots-food': 'https://4patriots.com/products/4week-food?drolid=0001',
        'rei-base-camp': 'https://www.rei.com/product/148555/rei-co-op-base-camp-4-tent',
        'msr-whisperlite': 'https://amzn.to/msrwhisperlite'
    }
    
    # Track the click
    click_data = {
        'product_id': product,
        'timestamp': datetime.utcnow(),
        'visitor_id': request.cookies.get('visitor_id', generate_visitor_id()),
        'referrer': request.referrer,
        'user_agent': request.user_agent.string
    }
    
    if isinstance(db, dict):
        db['affiliate_clicks'].append(click_data)
    else:
        db.affiliate_clicks.insert_one(click_data)
    
    return redirect(affiliate_links.get(product, '/gear'))

@app.route('/social/<platform>')
def social_redirect(platform):
    """Track and redirect social media clicks"""
    social_links = {
        'reddit': 'https://www.reddit.com/r/gorillacamping',
        'facebook': 'https://www.facebook.com/profile.php?id=61577334442896',
        'tiktok': 'https://www.tiktok.com/@gorillacamping',
        'instagram': 'https://www.instagram.com/gorillacamping',
        'youtube': 'https://www.youtube.com/@gorillacamping'
    }
    return redirect(social_links.get(platform, '/'))

@app.route('/api/analytics/summary')
def api_analytics_summary():
    """Return basic analytics for the dashboard"""
    api_key = request.args.get('api_key')
    if api_key != os.environ.get('ADMIN_API_KEY'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    if isinstance(db, dict):
        return jsonify({
            'affiliate_clicks': len(db['affiliate_clicks']),
            'subscribers': len(db['subscribers']),
            'ai_interactions': len(db['ai_usage']),
            'estimated_ai_cost': sum(item.get('estimated_cost', 0) for item in db['ai_usage']),
            'total_revenue_estimate': len(db['affiliate_clicks']) * 5.50  # Avg commission estimate
        })
    else:
        ai_cost = sum(item.get('estimated_cost', 0) for item in db.ai_usage.find({}, {'estimated_cost': 1}))
        return jsonify({
            'affiliate_clicks': db.affiliate_clicks.count_documents({}),
            'subscribers': db.subscribers.count_documents({}),
            'ai_interactions': db.ai_usage.count_documents({}),
            'estimated_ai_cost': ai_cost,
            'total_revenue_estimate': db.affiliate_clicks.count_documents({}) * 5.50
        })

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_DEBUG', 'False') == 'True')
