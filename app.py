import os
import re
import uuid
import random
import requests
from datetime import datetime, timedelta
from flask import Flask, request, render_template, jsonify, redirect, url_for, flash, session, Response, send_file, send_from_directory, make_response
from urllib.parse import urlparse, parse_qs
import traceback
import time

# --- HANDLE OPTIONAL DEPENDENCIES ---
try:
    from pymongo import MongoClient
    pymongo_available = True
except ImportError:
    print("⚠️ pymongo not installed, continuing without MongoDB features")
    MongoClient = None
    pymongo_available = False

# Import our AI optimizer
try:
    from ai_optimizer import AIOptimizer, ai_optimizer, optimize_ai_call
    ai_optimizer_available = True
except ImportError:
    print("⚠️ ai_optimizer dependencies not installed, continuing without AI optimization")
    AIOptimizer = None
    ai_optimizer = None
    optimize_ai_call = None
    ai_optimizer_available = False

try:
    from guerilla_personality import guerilla, memory
    guerilla_available = True
except ImportError:
    print("⚠️ guerilla_personality dependencies not installed, continuing without personality features")
    guerilla = None
    memory = None
    guerilla_available = False

try:
    import google.generativeai as genai
    genai_available = True
except ImportError:
    print("⚠️ google.generativeai not installed, continuing without AI features")
    genai = None
    genai_available = False

# --- FLASK SETUP ---
app = Flask(__name__, static_folder='static')
app.secret_key = os.environ.get('SECRET_KEY') or 'guerilla-camping-secret-2025'
app.config['SESSION_COOKIE_SECURE'] = True  # For HTTPS

# --- HANDLE OPTIONAL DEPENDENCIES ---
try:
    from flask_compress import Compress
    compress = Compress()
    compress.init_app(app)
    print("✅ Flask-Compress initialized")
except ImportError:
    print("⚠️ flask_compress not installed, continuing without compression")

# --- GEMINI AI SETUP ---
if genai_available:
    gemini_api_key = os.environ.get('GEMINI_API_KEY')
    if gemini_api_key:
        genai.configure(api_key=gemini_api_key)
        print("✅ Google Generative AI initialized")
    else:
        print("⚠️ GEMINI_API_KEY not set, AI features disabled")
        genai = None
else:
    print("⚠️ google.generativeai not installed, continuing without AI features")
    genai = None

# --- MONGODB SETUP ---
try:
    if pymongo_available:
        mongodb_uri = os.environ.get('MONGODB_URI')
        if mongodb_uri:
            client = MongoClient(mongodb_uri)
            db = client.get_default_database()
            # Test connection
            db.command('ping')
            print("✅ MongoDB connected successfully!")
        else:
            print("⚠️ No MongoDB URI found - running in demo mode")
            db = None
    else:
        print("⚠️ pymongo not available - running without MongoDB")
        db = None
except Exception as e:
    print(f"❌ MongoDB connection error: {e}")
    db = None

# Initialize AI optimizer
if ai_optimizer_available:
    ai_optimizer = AIOptimizer()
else:
    ai_optimizer = None

# --- HELPER FUNCTIONS ---
def log_event(event_type, message, level="INFO"):
    """Simple logging function"""
    print(f"{level}: {event_type} - {message}")
    if db is not None:
        try:
            db.logs.insert_one({
                "type": event_type,
                "message": message,
                "level": level,
                "timestamp": datetime.utcnow()
            })
        except Exception as e:
            print(f"❌ Error logging to MongoDB: {e}")


def ask_gemini_optimized(query, context="", user_id=""):
    """
    Optimized Gemini call with perfect Guerilla personality
    """
    try:
        # Check if dependencies are available
        if not genai_available or not guerilla_available:
            return "AI features not available - missing dependencies"
            
        # Get user context from conversation memory
        user_context = memory.get_context_for_ai()
        
        # Build the perfect Guerilla prompt
        personality_prompt = guerilla.get_personality_prompt()
        
        full_prompt = f"""
{personality_prompt}

USER CONTEXT: {user_context}
CONVERSATION CONTEXT: {context}

USER MESSAGE: {query}

Respond as Guerilla the Gorilla. Be authentic, concise, and helpful. Share real experience, not sales pitches.
"""

        # Initialize Gemini model
        model = genai.GenerativeModel('gemini-pro')
        
        # Generate response
        response = model.generate_content(full_prompt)
        ai_response = response.text
        
        # Apply Guerilla personality filters
        ai_response = guerilla.filter_response(ai_response)
        ai_response = guerilla.add_guerilla_touch(ai_response)
        
        # Learn from conversation
        memory.learn_from_conversation(query, ai_response)
        
        # Add conversation to history
        ai_optimizer.add_to_history(user_id, 'user', query)
        ai_optimizer.add_to_history(user_id, 'assistant', ai_response)
        
        # Get smart product recommendations
        user_history = ai_optimizer.get_conversation_history(user_id)
        recommendations = ai_optimizer.smart_product_recommendation(query, user_history)
        
        # Optimize response with recommendations
        final_response = ai_optimizer.optimize_response(ai_response, recommendations)
        
        return final_response
        
    except Exception as e:
        logger.error(f"Gemini error: {e}")
        
        # Authentic Guerilla fallback responses
        fallback_responses = [
            "System's taking a smoke break. Ask me again in a sec.",
            "Tech's acting up. But hey, what's your real question?",
            "Connection's wonky. Try that again?",
            "Servers are napping. Give it another shot.",
            "Network hiccup. What were you asking about?"
        ]
        
        import random
        return random.choice(fallback_responses)

# Apply AI optimization decorator if available
if ai_optimizer_available and optimize_ai_call:
    ask_gemini_optimized = optimize_ai_call(ask_gemini_optimized)

def get_default_gear_items():
    """Return default gear items with highest affiliate payouts"""
    return [
        {
            'name': 'Jackery Explorer 240',
            'image': 'https://m.media-amazon.com/images/I/41XePYWYlAL._AC_US300_.jpg',
            'description': 'Perfect for keeping devices charged off-grid. This paid for itself with just 2 viral videos I made from camp.',
            'affiliate_id': 'jackery-explorer-240',
            'price': '$199.99',
            'old_price': '$299.99',
            'savings': 'Save $100',
            'rating': 5,
            'badges': ['HOT DEAL', 'BEST VALUE'],
            'specs': ['240Wh', '250W output', 'Multiple ports'],
            'commission': '$6.00 (3%)'
        },
        {
            'name': 'LifeStraw Personal Water Filter',
            'image': 'https://m.media-amazon.com/images/I/71SYsNwj7hL._AC_UL320_.jpg',
            'description': 'Essential survival gear that filters 99.9999% of waterborne bacteria. My #1 affiliate earner!',
            'affiliate_id': 'lifestraw-filter',
            'price': '$14.96',
            'old_price': '$19.95',
            'savings': 'Save 25%',
            'rating': 5,
            'badges': ['BESTSELLER'],
            'specs': ['1000L capacity', 'No chemicals', 'Compact'],
            'commission': '$0.45 (3%)'
        }
    ]

def get_high_commission_gear():
    """Return high-commission gear (20-30% instead of Amazon's 3-4%)"""
    return [
        {
            'name': '4Patriots Emergency Food Kit',
            'image': 'https://via.placeholder.com/300x200?text=Emergency+Food',
            'description': 'My #1 recommended survival food - lasts 25 years and tastes great!',
            'affiliate_id': '4patriots-food',
            'price': '$197',
            'old_price': '$297',
            'commission': '$49.25 (25%)',  # vs $5.91 on Amazon (3%)
            'inventory': random.randint(2, 7),
            'affiliate_link': 'https://4patriots.com/products/4week-food?drolid=0001'
        },
        {
            'name': 'Alexapure Pro Water Filter',
            'image': 'https://via.placeholder.com/300x200?text=Water+Filter',
            'description': 'The ultimate off-grid water solution - I use this daily at camp.',
            'affiliate_id': 'alexapure-pro',
            'price': '$249',
            'old_price': '$349',
            'commission': '$74.70 (30%)',  # vs $7.47 on Amazon (3%)
            'inventory': random.randint(1, 5),
            'affiliate_link': 'https://4patriots.com/products/alexapure-pro?drolid=0001'
        }
    ]

def generate_visitor_id():
    """Generate a unique visitor ID for tracking"""
    return str(uuid.uuid4())

def track_page_view(page_name, source=None, metadata=None):
    """Track page view with metadata"""
    if db is None:
        return
        
    visitor_id = request.cookies.get('visitor_id', generate_visitor_id())
    
    view_data = {
        'page': page_name,
        'timestamp': datetime.utcnow(),
        'visitor_id': visitor_id,
        'user_agent': request.headers.get('User-Agent', ''),
        'ip_hash': hash(request.remote_addr) if request.remote_addr else None,
        'referrer': request.referrer
    }
    
    if source:
        view_data['source'] = source
        
    if metadata and isinstance(metadata, dict):
        view_data.update(metadata)
    
    try:
        db.page_views.insert_one(view_data)
    except Exception as e:
        print(f"❌ Error tracking page view: {e}")

# --- OPTIMIZED AI ROUTES ---

@app.route('/api/guerilla-chat', methods=['POST'])
def guerilla_chat():
    """
    Perfect Guerilla AI chat with optimization
    """
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({'error': 'Message is required'}), 400
        
        user_message = data['message']
        user_id = data.get('user_id', f"user_{int(time.time())}")
        context = data.get('context', '')
        
        # Get optimized response
        ai_response = ask_gemini_optimized(user_message, context, user_id)
        
        # Get analytics for monitoring
        analytics = ai_optimizer.get_analytics()
        
        response_data = {
            'response': ai_response,
            'user_id': user_id,
            'analytics': {
                'total_cost': f"${analytics['total_cost']:.4f}",
                'avg_response_time': f"{analytics['avg_response_time']:.2f}s",
                'total_calls': analytics['total_calls']
            }
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Chat error: {e}")
        return jsonify({
            'response': "Something went sideways. Try asking again.",
            'error': str(e)
        }), 500

@app.route('/api/optimize', methods=['POST'])
def optimize_endpoint():
    """
    Direct optimization endpoint for testing
    """
    try:
        data = request.get_json()
        query = data.get('query', '')
        
        if not query:
            return jsonify({'error': 'Query required'}), 400
        
        # Test the optimization system
        start_time = time.time()
        
        # Check cache
        cached = ai_optimizer.get_cached_response(query)
        if cached:
            response_time = time.time() - start_time
            return jsonify({
                'response': cached,
                'cache_hit': True,
                'response_time': f"{response_time:.3f}s",
                'cost_saved': True
            })
        
        # Generate new response
        ai_response = ask_gemini_optimized(query)
        response_time = time.time() - start_time
        
        analytics = ai_optimizer.get_analytics()
        
        return jsonify({
            'response': ai_response,
            'cache_hit': False,
            'response_time': f"{response_time:.3f}s",
            'analytics': analytics
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai-analytics', methods=['GET'])
def ai_analytics():
    """Get AI usage analytics"""
    analytics = ai_optimizer.get_analytics()
    return jsonify(analytics)

# --- EXISTING ROUTES (keeping the same) ---

@app.before_request
def redirect_www():
    """SEO Improvement: Redirect www to non-www for better SEO and analytics"""
    if request.host.startswith('www.'):
        url = request.url.replace('www.', '', 1)
        return redirect(url, code=301)

@app.route('/guerilla-bible')
def guerilla_bible():
    """The Guerilla Bible - Ultimate camping guide"""
    track_page_view('guerilla_bible')
    return render_template('guerilla_bible.html')

@app.route('/guerilla-stats')
def guerilla_stats():
    """Show site statistics and analytics"""
    if db is None:
        stats = {
            'total_visitors': 0,
            'total_page_views': 0,
            'ai_interactions': 0,
            'conversion_rate': 0
        }
    else:
        try:
            # Get basic stats
            total_visitors = db.page_views.distinct('visitor_id')
            total_page_views = db.page_views.count_documents({})
            ai_interactions = db.ai_interactions.count_documents({})
            
            # Calculate conversion rate (simplified)
            affiliate_clicks = db.affiliate_clicks.count_documents({}) if 'affiliate_clicks' in db.list_collection_names() else 0
            conversion_rate = (affiliate_clicks / max(total_page_views, 1)) * 100
            
            stats = {
                'total_visitors': len(total_visitors),
                'total_page_views': total_page_views,
                'ai_interactions': ai_interactions,
                'conversion_rate': round(conversion_rate, 2)
            }
        except Exception as e:
            print(f"Error getting stats: {e}")
            stats = {
                'total_visitors': 0,
                'total_page_views': 0,
                'ai_interactions': 0,
                'conversion_rate': 0
            }
    
    track_page_view('guerilla_stats')
    return render_template('guerilla_stats.html', stats=stats)

@app.route('/track/guerilla-view', methods=['POST'])
def track_guerilla_view():
    """Track when Guerilla mascot is viewed"""
    data = request.get_json()
    product_id = data.get('product_id', 'unknown')
    
    if db is not None:
        db.guerilla_views.insert_one({
            'product_id': product_id,
            'timestamp': datetime.utcnow(),
            'visitor_id': request.cookies.get('visitor_id', 'unknown')
        })
    
    return jsonify({'success': True})

@app.route('/track/guerilla-click', methods=['POST'])
def track_guerilla_click():
    """Track when Guerilla mascot is clicked"""
    data = request.get_json()
    product_id = data.get('product_id', 'unknown')
    
    if db is not None:
        db.guerilla_clicks.insert_one({
            'product_id': product_id,
            'timestamp': datetime.utcnow(),
            'visitor_id': request.cookies.get('visitor_id', 'unknown')
        })
    
    return jsonify({'success': True})

@app.route('/chat')
def live_chat():
    """
    Live chat interface - modern ChatGPT-style experience
    """
    return render_template('guerilla_chat_live.html')

@app.route('/ai-chat')
def ai_chat_redirect():
    """Redirect old chat to new interface"""
    return redirect('/chat')

# Update the main index to point to new chat
@app.route('/')
def index():
    """Homepage with link to new chat interface"""
    return render_template('index.html', chat_url='/chat')

@app.route('/blog')
def blog():
    """Blog page with camping articles"""
    track_page_view('blog')
    return render_template('blog.html')

@app.route('/api/gorilla-ai', methods=['POST'])
def gorilla_ai():
    """Gorilla AI assistant that recommends affiliate products"""
    data = request.json
    user_query = data.get('query', '')
    
    # Track analytics
    if db is not None:
        db.ai_interactions.insert_one({
            'query': user_query,
            'timestamp': datetime.utcnow(),
            'visitor_id': request.cookies.get('visitor_id', 'unknown')
        })
    
    # Check for product recommendation opportunities
    product_matches = []
    
    if any(word in user_query.lower() for word in ['power', 'battery', 'charging', 'electricity']):
        product_matches.append({
            'name': 'Jackery Explorer 240',
            'link': '/affiliate/jackery-explorer-240',
            'reason': 'perfect for keeping devices charged at camp'
        })
    
    if any(word in user_query.lower() for word in ['water', 'drink', 'thirsty', 'hydration']):
        product_matches.append({
            'name': 'LifeStraw Filter',
            'link': '/affiliate/lifestraw-filter',
            'reason': 'ensures safe drinking water from any source'
        })
        
    if any(word in user_query.lower() for word in ['food', 'eat', 'hungry', 'meal', 'cook']):
        product_matches.append({
            'name': '4Patriots Food Kit',
            'link': '/affiliate/4patriots-food',
            'reason': '25-year shelf life emergency food'
        })
    
    # Generate AI response
    try:
        ai_response = ask_gemini_optimized(user_query)
        
        # Add subtle product recommendations
        if product_matches:
            ai_response += "\n\n🦍 GORILLA RECOMMENDS:\n"
            for product in product_matches:
                ai_response += f"• [{product['name']}]({product['link']}) - {product['reason']}\n"
        
        return jsonify({
            'success': True,
            'response': ai_response,
            'recommendations': product_matches
        })
    except Exception as e:
        print(f"AI Error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/blog/<slug>')
def post(slug):
    """Individual blog post"""
    track_page_view(f'blog_post_{slug}')
    return render_template('post.html', slug=slug)

@app.route('/gear')
def gear():
    """Gear page with affiliate products"""
    track_page_view('gear')
    gear_items = get_default_gear_items()
    return render_template('gear.html', gear_items=gear_items)

@app.route('/premium-gear')
def premium_gear():
    """Premium gear with high commission rates"""
    track_page_view('premium_gear')
    high_commission_items = get_high_commission_gear()
    return render_template('premium_gear.html', gear_items=high_commission_items)

@app.route('/about')
def about():
    """About page"""
    track_page_view('about')
    return render_template('about.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    """Contact page with form"""
    if request.method == 'POST':
        name = request.form.get('name', '')
        email = request.form.get('email', '')
        message = request.form.get('message', '')
        
        # Log contact form submission
        if db is not None:
            db.contact_submissions.insert_one({
                'name': name,
                'email': email,
                'message': message,
                'timestamp': datetime.utcnow(),
                'visitor_id': request.cookies.get('visitor_id', 'unknown')
            })
        
        log_event("contact_form", f"Contact form submitted by {name} ({email})")
        flash('Thanks for reaching out! I\'ll get back to you soon.', 'success')
        return redirect(url_for('contact'))
    
    track_page_view('contact')
    return render_template('contact.html')

@app.route('/student-pack-strategy')
def student_pack_strategy():
    """Student developer pack strategy guide"""
    track_page_view('student_pack_strategy')
    return render_template('student_pack_strategy.html')

@app.route('/affiliate/<product_id>')
def affiliate_redirect(product_id):
    """Redirect to affiliate product with tracking"""
    visitor_id = request.cookies.get('visitor_id', 'unknown')
    
    # Track affiliate click
    if db is not None:
        db.affiliate_clicks.insert_one({
            'product_id': product_id,
            'timestamp': datetime.utcnow(),
            'visitor_id': visitor_id,
            'referrer': request.referrer,
            'user_agent': request.headers.get('User-Agent', '')
        })
    
    # Product mapping
    product_links = {
        'jackery-explorer-240': 'https://amzn.to/3QZqX8Y',
        'lifestraw-filter': 'https://amzn.to/3QZqX8Y',
        '4patriots-food': 'https://4patriots.com/products/4week-food?drolid=0001',
        'alexapure-pro': 'https://4patriots.com/products/alexapure-pro?drolid=0001'
    }
    
    affiliate_link = product_links.get(product_id, 'https://gorillacamping.site/gear')
    
    log_event("affiliate_click", f"Affiliate click: {product_id} by {visitor_id}")
    return redirect(affiliate_link)

@app.route('/social/<platform>')
def social_redirect(platform):
    """Redirect to social media platforms"""
    social_links = {
        'youtube': 'https://youtube.com/@gorillacamping',
        'instagram': 'https://instagram.com/gorillacamping',
        'tiktok': 'https://tiktok.com/@gorillacamping',
        'twitter': 'https://twitter.com/gorillacamping'
    }
    
    target_url = social_links.get(platform, 'https://gorillacamping.site')
    
    # Track social media click
    if db is not None:
        db.social_clicks.insert_one({
            'platform': platform,
            'timestamp': datetime.utcnow(),
            'visitor_id': request.cookies.get('visitor_id', 'unknown')
        })
    
    log_event("social_click", f"Social click: {platform}")
    return redirect(target_url)

@app.route('/subscribe', methods=['POST'])
def subscribe():
    """Email subscription endpoint"""
    email = request.form.get('email', '').strip()
    source = request.form.get('source', 'general')
    
    if not email or '@' not in email:
        flash('Please enter a valid email address.', 'error')
        return redirect(request.referrer or url_for('home'))
    
    # Check if already subscribed
    if db is not None:
        existing = db.subscribers.find_one({'email': email})
        if existing:
            flash('You\'re already subscribed! Thanks for the support.', 'info')
            return redirect(request.referrer or url_for('home'))
        
        # Add new subscriber
        db.subscribers.insert_one({
            'email': email,
            'source': source,
            'timestamp': datetime.utcnow(),
            'visitor_id': request.cookies.get('visitor_id', 'unknown'),
            'active': True
        })
    
    log_event("email_subscription", f"New subscriber: {email} from {source}")
    flash('Welcome to the Guerilla family! Check your email for exclusive camping tips.', 'success')
    return redirect(request.referrer or url_for('home'))

@app.route('/guerilla-guide')
def guerilla_guide():
    """The Guerilla Guide to camping"""
    track_page_view('guerilla_guide')
    return render_template('guerilla_guide.html')

@app.route('/digital-busking')
def digital_busking():
    """Digital busking guide"""
    track_page_view('digital_busking')
    return render_template('digital_busking.html')

@app.route('/thank-you')
def thank_you():
    """Thank you page"""
    track_page_view('thank_you')
    return render_template('thank_you.html')

@app.route('/high-commission-gear')
def high_commission_gear():
    """High commission gear page"""
    track_page_view('high_commission_gear')
    high_commission_items = get_high_commission_gear()
    return render_template('high_commission_gear.html', gear_items=high_commission_items)

@app.route('/guerilla-ai-system')
def guerilla_ai_system():
    """Guerilla AI system page"""
    track_page_view('guerilla_ai_system')
    return render_template('guerilla_ai_system.html')

@app.route('/30day-challenge')
def challenge():
    """30-day camping challenge"""
    track_page_view('30day_challenge')
    return render_template('30day_challenge.html')

@app.route('/growing-guides')
def growing_guides():
    """Growing guides page"""
    track_page_view('growing_guides')
    return render_template('growing_guides.html')

@app.route('/sms-signup', methods=['POST'])
def sms_signup():
    """SMS subscription endpoint"""
    phone = request.form.get('phone', '').strip()
    source = request.form.get('source', 'general')
    
    if not phone or len(phone) < 10:
        flash('Please enter a valid phone number.', 'error')
        return redirect(request.referrer or url_for('home'))
    
    # Track SMS signup
    if db is not None:
        db.sms_subscribers.insert_one({
            'phone': phone,
            'source': source,
            'timestamp': datetime.utcnow(),
            'visitor_id': request.cookies.get('visitor_id', 'unknown'),
            'active': True
        })
    
    log_event("sms_subscription", f"New SMS subscriber: {phone} from {source}")
    flash('Thanks! You\'ll get camping tips and deals via SMS.', 'success')
    return redirect(request.referrer or url_for('home'))

@app.route('/ai-membership')
def ai_membership():
    """AI membership page"""
    track_page_view('ai_membership')
    return render_template('ai_membership.html')

@app.route('/robots.txt')
def robots():
    """Robots.txt for SEO"""
    return Response("""
User-agent: *
Allow: /
Disallow: /admin/
Disallow: /api/
Sitemap: https://gorillacamping.site/sitemap.xml
""", mimetype='text/plain')

@app.route('/favicon.ico')
def favicon():
    """Favicon"""
    return send_from_directory('static', 'favicon.ico')

@app.errorhandler(404)
def page_not_found(e):
    """404 error handler"""
    return render_template('404.html'), 404

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000))) 