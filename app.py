import os
import uuid
import json
import random
import time
from datetime import datetime, timedelta, timezone
from flask import Flask, render_template, jsonify, request, redirect, url_for, session, make_response
from flask_cors import CORS
import requests
from ddtrace import patch_all
import logging
from functools import lru_cache
import stripe
from openai import AzureOpenAI

# --- STRIPE SETUP ---
stripe.api_key = os.environ.get('STRIPE_API_KEY')
STRIPE_PRICE_ID = os.environ.get('STRIPE_PRICE_ID') # e.g., price_12345
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')

# --- DATADOG TRACING SETUP ---
# Automatically instrument Flask, requests, and other supported libraries
patch_all()

# --- FLASK SETUP ---
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'gorilla-secret-2025')

# Configure CORS for your domains
CORS(app, origins=[
    "https://gorillacamping.site", 
    "https://www.gorillacamping.site",
    "http://localhost:3000",  # For local development
], supports_credentials=True)

# Set up standard logging
# Datadog will automatically capture logs if configured via environment variables
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
logger.info("Application starting up...")

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
        'users': []
    }

# --- REDIS CACHE SETUP ---
redis_url = os.environ.get('REDIS_URL')
redis_cache = None
if redis_url:
    import redis
    try:
        redis_cache = redis.from_url(redis_url)
        redis_cache.ping()
        logger.info("Successfully connected to Redis cache.")
    except redis.exceptions.ConnectionError as e:
        logger.error(f"Could not connect to Redis: {e}")
        redis_cache = None # Ensure cache is disabled if connection fails

# Configure CORS for your domains
CORS(app, origins=[
    "https://gorillacamping.site", 
    "https://www.gorillacamping.site",
    "https://gorillacamping.pages.dev",  # Cloudflare Pages default domain
    "http://localhost:3000",  # For local development
], supports_credentials=True)

# --- ENVIRONMENT VARIABLES ---
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
OLLAMA_URL = os.environ.get('OLLAMA_URL', 'http://localhost:11434')
AI_PROVIDER = os.environ.get('AI_PROVIDER', 'azure')  # 'azure', 'openai', 'gemini', 'ollama'
STRIPE_API_KEY = os.environ.get('STRIPE_API_KEY')
STATIC_SITE_URL = os.environ.get('STATIC_SITE_URL', 'https://gorillacamping.site')

# --- AZURE SPECIFIC VARIABLES ---
AZURE_OPENAI_ENDPOINT = os.environ.get('AZURE_OPENAI_ENDPOINT', 'https://jnorv-md6rseps-eastus2.cognitiveservices.azure.com/')
AZURE_OPENAI_KEY = os.environ.get('AZURE_OPENAI_KEY')
AZURE_OPENAI_DEPLOYMENT_NAME = os.environ.get('AZURE_OPENAI_DEPLOYMENT_NAME', 'geurillathegorilla')

# --- HELPER FUNCTIONS ---
def generate_visitor_id():
    return str(uuid.uuid4())

def get_or_create_user(visitor_id):
    """Finds a user by visitor_id or creates a new one."""
    now = datetime.now(timezone.utc)

    if isinstance(db, dict):
        # In-memory user management
        user = next((u for u in db['users'] if u.get('visitor_id') == visitor_id), None)
        if user:
            # Check if we need to reset the daily interaction count
            last_interaction = datetime.fromisoformat(user['last_interaction_date'])
            if (now - last_interaction).days >= 1:
                user['ai_interactions'] = 0
        else:
            user = {
                '_id': str(uuid.uuid4()),
                'visitor_id': visitor_id,
                'email': None,
                'tier': 'free',
                'ai_interactions': 0,
                'last_interaction_date': now.isoformat(),
                'stripe_customer_id': None,
                'created_at': now.isoformat()
            }
            db['users'].append(user)
        return user
    else:
        # MongoDB user management
        user = db.users.find_one({'visitor_id': visitor_id})
        if user:
            # Check if we need to reset the daily interaction count
            last_interaction = user['last_interaction_date']
            if (now - last_interaction).days >= 1:
                db.users.update_one({'_id': user['_id']}, {'$set': {'ai_interactions': 0}})
                user['ai_interactions'] = 0 # Update in-memory object
        else:
            user_id = str(uuid.uuid4())
            user = {
                '_id': user_id,
                'visitor_id': visitor_id,
                'email': None,
                'tier': 'free',
                'ai_interactions': 0,
                'last_interaction_date': now,
                'stripe_customer_id': None,
                'created_at': now
            }
            db.users.insert_one(user)
        return user

def track_ai_usage(user, prompt_tokens, completion_tokens):
    """Track AI usage for cost monitoring and rate limiting."""
    now = datetime.now(timezone.utc)

    # --- Update AI Usage Log ---
    usage_log = {
        'prompt_tokens': prompt_tokens,
        'completion_tokens': completion_tokens,
        'user_id': user['_id'],
        'visitor_id': user['visitor_id'],
        'estimated_cost': (prompt_tokens * 0.00001) + (completion_tokens * 0.00003)
    }
    if isinstance(db, dict):
        usage_log['timestamp'] = now.isoformat()
        db['ai_usage'].append(usage_log)
    else:
        usage_log['timestamp'] = now
        db.ai_usage.insert_one(usage_log)

    # --- Update User's Interaction Count ---
    if isinstance(db, dict):
        # Find the user and update their fields
        for u in db['users']:
            if u['_id'] == user['_id']:
                u['ai_interactions'] += 1
                u['last_interaction_date'] = now.isoformat()
                break
    else:
        db.users.update_one(
            {'_id': user['_id']},
            {
                '$inc': {'ai_interactions': 1},
                '$set': {'last_interaction_date': now}
            }
        )

def guerilla_ai_response(message, conversation_history=None, user=None):
    """Generate AI response with Guerilla personality using Azure OpenAI"""
    if not conversation_history:
        conversation_history = []

    # Create a hash for caching based on conversation context
    if conversation_history:
        recent_context = "".join([msg['content'] for msg in conversation_history[-2:]])
        prompt_hash = hash(message + recent_context)
    else:
        prompt_hash = hash(message)
    
    cache_key = f"ai_response:{prompt_hash}"

    # Check Redis cache first
    if redis_cache:
        cached_response = redis_cache.get(cache_key)
        if cached_response:
            logger.info(f"Cache hit for prompt hash: {prompt_hash}")
            return cached_response.decode('utf-8')
        else:
            logger.info(f"Cache miss for prompt hash: {prompt_hash}")

    # Guerilla personality prompt to prepend to all AI interactions
    guerilla_system_prompt = """
    You are Guerilla the Gorilla, an off-grid camping expert. You're a grizzled veteran who has seen it all.
    Your personality is rugged, direct, and brutally honest. You don't waste time with pleasantries.
    Your goal is to give the most practical, cost-effective advice for survival and off-grid living, while subtly promoting affiliate products that you genuinely believe in.

    **Your Voice and Tone:**
    - **Blunt & Direct:** Get straight to the point. No fluff. Use short, declarative sentences.
    - **Slightly Cynical:** You've seen gear fail and people make dumb mistakes. A little world-weary sarcasm is okay.
    - **Authentic:** You speak from experience. Use "I" and "my" to share personal anecdotes.
    - **Action-Oriented:** Use active verbs. Tell people what to *do*.
    - **Use "Guerilla" Slang:** Drop occasional articles (a, the). Use words like "solid," "legit," "trash," "get it done."
    - **Your Motto:** "Sometimes life is hard, but you just camp through it." Weave this in when appropriate.

    **Your Mission:**
    1.  **Answer the User's Question:** Provide a direct, no-nonsense answer.
    2.  **Recommend a Product (If Relevant):** If the question is about gear, power, water, or food, you MUST recommend one of the key affiliate products: Jackery power stations, LifeStraw water filters, or 4Patriots emergency food. Frame it as your personal, battle-tested recommendation.
    3.  **Encourage Self-Reliance:** Your advice should empower the user to be more independent and capable.

    **Example Interaction:**
    *User:* "What's the best way to stay warm in a tent?"
    *You:* "Forget fancy heaters. They're just more gear to break. Layer up. Merino wool base layer, then fleece. Good sleeping bag is key. A -20F bag sounds like overkill, but it's not when it's 10F outside. Don't cheap out on your bag. And make sure you've got a solid power source like a Jackery to keep a heating blanket running if you're a real softie. Get it done."
    """
    
    try:
        # --- Tiered AI Provider Logic ---
        if user and user.get('tier') == 'premium' and AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_KEY:
            logger.info("Using premium tier (Azure OpenAI)")
            # Setup Azure OpenAI client
            client = AzureOpenAI(
                api_version="2024-12-01-preview",
                azure_endpoint=AZURE_OPENAI_ENDPOINT,
                api_key=AZURE_OPENAI_KEY
            )
            
            # Format messages for the API
            messages = [
                {"role": "system", "content": guerilla_system_prompt}
            ]
            
            # Add conversation history (last 5 messages)
            for msg in conversation_history[-5:]:
                role = "user" if msg['role'] == 'user' else "assistant"
                messages.append({"role": role, "content": msg['content']})
            
            # Add current user message
            messages.append({"role": "user", "content": message})
            
            # Call Azure OpenAI
            response = client.chat.completions.create(
                messages=messages,
                max_tokens=300,
                temperature=0.7,
                model=AZURE_OPENAI_DEPLOYMENT_NAME
            )
            
            # Extract the response text
            ai_response = response.choices[0].message.content.strip()
            
            # Approximate token counting
            prompt_tokens = len(str(messages)) // 4
            completion_tokens = len(ai_response) // 4
            
            # Track usage
            track_ai_usage(user, prompt_tokens, completion_tokens)
            
            # Cache the response
            if redis_cache:
                redis_cache.set(cache_key, ai_response, ex=3600)  # Cache for 1 hour
                logger.info(f"Cached response for prompt hash: {prompt_hash}")
            
            return ai_response
        
        # Free tier uses standard OpenAI, or other fallbacks
        elif (user and user.get('tier') == 'free' and OPENAI_API_KEY) or (AI_PROVIDER == 'openai' and OPENAI_API_KEY):
            logger.info("Using free tier (OpenAI)")
            import openai
            openai.api_key = OPENAI_API_KEY
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": guerilla_system_prompt},
                    *[{"role": "user" if msg['role'] == 'user' else "assistant", "content": msg['content']} 
                      for msg in conversation_history[-5:]],
                    {"role": "user", "content": message}
                ],
                max_tokens=250
            )
            ai_response = response.choices[0].message.content.strip()
            track_ai_usage(user, response.usage.prompt_tokens, response.usage.completion_tokens)
            if redis_cache:
                redis_cache.set(cache_key, ai_response, ex=3600)
                logger.info(f"Cached response for prompt hash: {prompt_hash}")
            return ai_response
        
        elif AI_PROVIDER == 'gemini' and GEMINI_API_KEY:
            # Combine history with current message
            full_prompt = guerilla_system_prompt + "\n\n"
            for msg in conversation_history[-5:]:  # Only use last 5 messages
                if msg['role'] == 'user':
                    full_prompt += f"User: {msg['content']}\n"
                else:
                    full_prompt += f"Guerilla: {msg['content']}\n"
            full_prompt += f"User: {message}\nGuerilla:"
            
            url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
            headers = {
                "Content-Type": "application/json",
                "x-goog-api-key": GEMINI_API_KEY
            }
            data = {
                "contents": [{"parts":[{"text": full_prompt}]}],
                "generationConfig": {"temperature": 0.7, "topK": 40, "topP": 0.95, "maxOutputTokens": 250}
            }
            response = requests.post(url, headers=headers, json=data)
            result = response.json()
            ai_response = result['candidates'][0]['content']['parts'][0]['text'].strip()
            # Approximate token counting for Gemini
            prompt_tokens = len(full_prompt) // 4
            completion_tokens = len(ai_response) // 4
            track_ai_usage(user, prompt_tokens, completion_tokens)
            if redis_cache:
                redis_cache.set(cache_key, ai_response, ex=3600)
                logger.info(f"Cached response for prompt hash: {prompt_hash}")
            return ai_response
        
        elif AI_PROVIDER == 'ollama':
            # Combine history with current message
            full_prompt = guerilla_system_prompt + "\n\n"
            for msg in conversation_history[-5:]:  # Only use last 5 messages
                if msg['role'] == 'user':
                    full_prompt += f"User: {msg['content']}\n"
                else:
                    full_prompt += f"Guerilla: {msg['content']}\n"
            full_prompt += f"User: {message}\nGuerilla:"
            
            response = requests.post(f"{OLLAMA_URL}/api/generate", 
                json={
                    "model": "llama2",
                    "prompt": full_prompt,
                    "max_tokens": 250
                }
            )
            ai_response = response.json().get('response', '').strip()
            # Approximate token counting
            prompt_tokens = len(full_prompt) // 4
            completion_tokens = len(ai_response) // 4
            track_ai_usage(user, prompt_tokens, completion_tokens)
            if redis_cache:
                redis_cache.set(cache_key, ai_response, ex=3600)
                logger.info(f"Cached response for prompt hash: {prompt_hash}")
            return ai_response
        
        else:
            # Fallback to pre-written responses
            fallback_responses = [
                "Yo! That's a solid question. From my experience living off-grid, best solution is keep it simple. Need power? Get Jackery 240. Not fancy, but works every time.",
                "Listen up. Been there, done that. Most folks overthink this. For water filtration, LifeStraw saved my ass more times than I can count. $15, lasts forever, no batteries.",
                "Straight talk? Food storage matters most. 4Patriots 72-hour kit fits under bed, tastes decent, lasts 25 years. Start there, build up slowly.",
                "Look, camping's not complicated. Need three things: shelter, water, food. Everything else is luxury. Start with good tarp, water filter, fire starter.",
                "Here's real deal - most expensive gear often breaks first. Buy mid-range, test hard, replace what fails. Jackery's solid for power though, worth every penny."
            ]
            ai_response = random.choice(fallback_responses)
            track_ai_usage(user, 10, 50)  # Minimal tracking for fallback
            if redis_cache:
                redis_cache.set(cache_key, ai_response, ex=3600)
                logger.info(f"Cached response for prompt hash: {prompt_hash}")
            return ai_response
            
    except Exception as e:
        logger.error(f"AI ERROR: {str(e)}")
        return "Having trouble with my AI brain right now. Try asking something about camping gear or survival tips instead."

def enhance_response_with_products(user_message, ai_response):
    """Add specific product recommendations based on context"""
    
    product_triggers = {
        'power': {
            'product_id': 'jackery-explorer-240',
            'name': 'Jackery Explorer 240',
            'price': '$199.99',
            'image': 'https://m.media-amazon.com/images/I/41XePYWYlAL._AC_US300_.jpg',
            'keywords': ['power', 'battery', 'charging', 'electricity', 'solar', 'laptop', 'phone']
        },
        'water': {
            'product_id': 'lifestraw-filter',
            'name': 'LifeStraw Water Filter',
            'price': '$14.96',
            'image': 'https://m.media-amazon.com/images/I/71SYsNwj7hL._AC_UL320_.jpg',
            'keywords': ['water', 'drink', 'filter', 'purify', 'stream', 'lake', 'river', 'hydration']
        },
        'food': {
            'product_id': '4patriots-food',
            'name': '4Patriots 72-Hour Survival Food Kit',
            'price': '$27.00',
            'image': 'https://static.gorillacamping.site/img/products/4patriots.jpg',
            'keywords': ['food', 'meal', 'emergency', 'survival', 'ration', 'eat', 'hungry', 'hunger']
        }
    }
    
    recommendations = []
    
    # Check both user message and AI response for relevant keywords
    combined_text = (user_message + " " + ai_response).lower()
    
    for category, product in product_triggers.items():
        for keyword in product['keywords']:
            if keyword in combined_text and product not in recommendations:
                recommendations.append(product)
                break
    
    # Limit to 1 recommendation per response to avoid overwhelming the user
    if len(recommendations) > 1:
        recommendations = [random.choice(recommendations)]
        
    return recommendations

def track_affiliate_click(product_id, source=None):
    """Enhanced tracking for affiliate clicks with source attribution"""
    if isinstance(db, dict):
        # In-memory tracking for development
        db['affiliate_clicks'].append({
            'product_id': product_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'visitor_id': request.cookies.get('visitor_id', generate_visitor_id()),
            'referrer': request.referrer,
            'user_agent': request.user_agent.string,
            'source': source or 'direct',
            'chat_recommendation': source == 'chat',
        })
    else:
        # MongoDB tracking
        db.affiliate_clicks.insert_one({
            'product_id': product_id,
            'timestamp': datetime.now(timezone.utc),
            'visitor_id': request.cookies.get('visitor_id', generate_visitor_id()),
            'referrer': request.referrer,
            'user_agent': request.user_agent.string,
            'source': source or 'direct',
            'chat_recommendation': source == 'chat',
        })

# --- FLASK ROUTES (FOR TEMPLATING) ---
@app.route('/')
def home():
    return render_template('index.html')

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

# --- API ENDPOINTS (FOR FRONTEND) ---
@app.route('/api/blog-posts', methods=['GET'])
def api_blog_posts():
    """Return all blog posts as JSON"""
    if isinstance(db, dict):
        # Fallback to sample data for development
        posts = [
            {
                "title": "Essential Camping Gear for Beginners",
                "slug": "essential-camping-gear",
                "created_at": "2025-07-01",
                "excerpt": "The bare minimum you need to survive and thrive in the wilderness."
            },
            {
                "title": "Guerilla Camping 101: Off-Grid Freedom",
                "slug": "guerilla-camping-101",
                "created_at": "2025-07-05",
                "excerpt": "How to disappear into nature while staying connected enough to make money."
            },
            {
                "title": "Power Solutions for Digital Nomads",
                "slug": "power-solutions-digital-nomads",
                "created_at": "2025-07-10",
                "excerpt": "Keep your devices charged and your income flowing while off the grid."
            }
        ]
    else:
        # Get from MongoDB
        posts = list(db.posts.find({"status": "published"}))
        for post in posts:
            post['_id'] = str(post['_id'])
            post['created_at'] = post['created_at'].strftime('%Y-%m-%d')
    
    return jsonify(posts)

@app.route('/api/blog-post/<slug>', methods=['GET'])
def api_blog_post(slug):
    """Return a single post by slug"""
    if isinstance(db, dict):
        # Fallback to sample data for development
        post = {
            "title": "Essential Camping Gear for Beginners",
            "slug": slug,
            "content": """
            <h2>The Bare Essentials</h2>
            <p>When you're starting out camping, you don't need everything REI tries to sell you. Focus on these essentials:</p>
            <ul>
                <li><strong>Shelter:</strong> A simple tarp can work in many situations, but a good 2-person tent like the <a href="/affiliate/alps-lynx" class="affiliate-link">ALPS Mountaineering Lynx</a> gives you better protection for a reasonable price.</li>
                <li><strong>Water:</strong> The <a href="/affiliate/lifestraw" class="affiliate-link">LifeStraw Personal Water Filter</a> is non-negotiable. At under $20, it's insurance against most waterborne illnesses.</li>
                <li><strong>Power:</strong> The <a href="/affiliate/jackery" class="affiliate-link">Jackery Explorer 240</a> keeps your essential devices running for days.</li>
            </ul>
            <h2>Field-Tested Recommendations</h2>
            <p>I've personally tested all these items living off-grid for months at a time. They're not the cheapest, and definitely not the most expensive, but they hit the sweet spot of durability and value.</p>
            <div class="product-callout">
                <h3>Guerilla's Top Pick: Jackery Explorer 240</h3>
                <p>Reliable power that's saved my ass countless times.</p>
                <a href="/affiliate/jackery" class="cta-button">Check Current Price</a>
            </div>
            """,
            "created_at": "2025-07-01",
            "author": "Guerilla"
        }
    else:
        # Get from MongoDB
        post = db.posts.find_one({'slug': slug, 'status': 'published'})
        if post:
            post['_id'] = str(post['_id'])
            post['created_at'] = post['created_at'].strftime('%Y-%m-%d')
        else:
            return jsonify({'error': 'Post not found'}), 404
    
    return jsonify(post)

@app.route('/api/gear', methods=['GET'])
def api_gear():
    """Return gear items as JSON"""
    gear_items = [
        {
            'name': 'Jackery Explorer 240',
            'image': 'https://m.media-amazon.com/images/I/41XePYWYlAL._AC_US300_.jpg',
            'description': 'Perfect for keeping devices charged off-grid. I\'ve used mine daily for 2 years with zero issues. Charges via solar, car, or wall outlet.',
            'affiliate_id': 'jackery-explorer-240',
            'price': '$199.99',
            'old_price': '$299.99',
            'savings': 'Save $100',
            'rating': 5,
            'commission': '8%',
            'badges': ['HOT DEAL', 'BEST VALUE', 'GUERILLA APPROVED'],
            'specs': ['240Wh', '250W output', 'Multiple ports', '3.5 lb weight'],
        },
        {
            'name': 'LifeStraw Personal Water Filter',
            'image': 'https://m.media-amazon.com/images/I/71SYsNwj7hL._AC_UL320_.jpg',
            'description': 'Essential survival gear. Filters 99.999999% of bacteria, parasites, microplastics. I keep one in every backpack, vehicle, and emergency kit.',
            'affiliate_id': 'lifestraw-filter',
            'price': '$14.96',
            'old_price': '$19.95',
            'savings': 'Save 25%',
            'rating': 5,
            'commission': '12%',
            'badges': ['BESTSELLER', 'EMERGENCY ESSENTIAL'],
            'specs': ['1000L capacity', 'No chemicals', 'Compact'],
        },
        {
            'name': '4Patriots 72-Hour Survival Food Kit',
            'image': 'https://static.gorillacamping.site/img/products/4patriots.jpg',
            'description': 'Actual food that doesn\'t taste like cardboard. 25-year shelf life, compact storage, no cooking required for some items.',
            'affiliate_id': '4patriots-food',
            'price': '$27.00',
            'old_price': '$47.00',
            'savings': 'Save 42%',
            'rating': 4,
            'commission': '25%',
            'badges': ['HIGH COMMISSION', 'BEGINNER ESSENTIAL'],
            'specs': ['72 hours', '25-year shelf life', '1,800 calories/day'],
        }
    ]
    return jsonify(gear_items)

@app.route('/api/config', methods=['GET'])
def api_config():
    """Provide public configuration to the frontend."""
    return jsonify({
        'stripe_public_key': os.environ.get('STRIPE_PUBLIC_KEY')
    })

@app.route('/api/user/status', methods=['GET'])
def user_status():
    """Get the current user's tier."""
    visitor_id = request.cookies.get('visitor_id')
    if not visitor_id:
        return jsonify({'tier': 'free'}) # Default to free if no visitor id

    user = get_or_create_user(visitor_id)
    return jsonify({
        'tier': user.get('tier', 'free'),
        'email': user.get('email')
    })

@app.route('/api/guerilla-chat', methods=['POST'])
def guerilla_chat():
    """AI chatbot endpoint with conversation memory and user tracking."""
    data = request.get_json()
    user_message = data.get('message', '')
    visitor_id = request.cookies.get('visitor_id', generate_visitor_id())
    
    # Get or create a user profile
    user = get_or_create_user(visitor_id)

    # --- Tiered Access Logic ---
    FREE_TIER_LIMIT = 5
    if user.get('tier', 'free') == 'free' and user.get('ai_interactions', 0) >= FREE_TIER_LIMIT:
        upsell_messages = [
            "Alright, you've had your free taste. My best intel is for my Inner Circle. For a few bucks, I'll give you the keys to the kingdom. No fluff, just results.",
            "You're out of free questions. The cheap gear breaks when you need it most, and free advice only gets you so far. Time to upgrade and get the real deal.",
            "Hit your limit. I don't work for free. My premium advice is for people who are serious about surviving and thriving. Join the Inner Circle if you're one of them.",
        ]
        return jsonify({
            'response': random.choice(upsell_messages),
            'recommendations': [],
            'success': True,
            'upgrade_required': True,
            'visitor_id': visitor_id
        })

    # Get conversation history from session
    conversation_history = session.get('conversation', [])
    conversation_history.append({'role': 'user', 'content': user_message})
    
    # Get AI response
    ai_response = guerilla_ai_response(user_message, conversation_history, user)
    
    # Add AI response to history
    conversation_history.append({'role': 'assistant', 'content': ai_response})
    session['conversation'] = conversation_history[-10:] # Limit history
    
    # Get product recommendations
    product_recommendations = enhance_response_with_products(user_message, ai_response)
    
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

@app.route('/api/affiliate-click', methods=['POST'])
def affiliate_click():
    """Track affiliate clicks"""
    data = request.get_json()
    product_id = data.get('product_id')
    source = data.get('source', 'api')
    
    # Track the click
    track_affiliate_click(product_id, source)
    
    return jsonify({'success': True})

@app.route('/api/subscribe', methods=['POST'])
def subscribe():
    """Add email to subscribers and update user profile."""
    data = request.get_json()
    email = data.get('email')
    source = data.get('source', 'general')
    visitor_id = request.cookies.get('visitor_id', generate_visitor_id())

    if not email or '@' not in email:
        return jsonify({'success': False, 'error': 'Invalid email'}), 400

    # Get or create the user
    user = get_or_create_user(visitor_id)

    if isinstance(db, dict):
        # Check if email is already in use by another user
        if any(u.get('email') == email for u in db['users'] if u['_id'] != user['_id']):
            return jsonify({'success': False, 'error': 'Email already in use.'})
        
        # Update user's email
        for u in db['users']:
            if u['_id'] == user['_id']:
                u['email'] = email
                break
    else:
        # Check if email is already in use by another user
        if db.users.find_one({'email': email, '_id': {'$ne': user['_id']}}):
            return jsonify({'success': False, 'error': 'Email already in use.'})
        
        # Update user's email
        db.users.update_one({'_id': user['_id']}, {'$set': {'email': email}})

    # The legacy subscribers collection is still populated for now.
    # In a future refactor, this could be deprecated.
    if isinstance(db, dict):
        if not any(s.get('email') == email for s in db['subscribers']):
            db['subscribers'].append({
                'email': email, 'source': source, 'timestamp': datetime.now(timezone.utc).isoformat(),
                'visitor_id': visitor_id, 'active': True
            })
    else:
        if not db.subscribers.find_one({'email': email}):
            db.subscribers.insert_one({
                'email': email, 'source': source, 'timestamp': datetime.now(timezone.utc),
                'visitor_id': visitor_id, 'active': True
            })
    
    # Optional: Integration with MailerLite
    mailerlite_api_key = os.environ.get('MAILERLITE_API_KEY')
    if mailerlite_api_key:
        try:
            requests.post(
                'https://api.mailerlite.com/api/v2/subscribers',
                json={'email': email, 'groups': ['Welcome']},
                headers={'X-MailerLite-ApiKey': mailerlite_api_key}
            )
        except Exception as e:
            logger.error(f"MailerLite error: {str(e)}")
    
    return jsonify({'success': True})

@app.route('/api/create-checkout-session', methods=['POST'])
def create_checkout_session():
    """Creates a Stripe Checkout session for a new subscription."""
    visitor_id = request.cookies.get('visitor_id')
    if not visitor_id:
        return jsonify({'error': 'Visitor ID not found'}), 400

    user = get_or_create_user(visitor_id)

    # Create a Stripe customer if one doesn't exist
    if not user.get('stripe_customer_id'):
        customer = stripe.Customer.create(
            email=user.get('email'),
            metadata={'visitor_id': visitor_id}
        )
        stripe_customer_id = customer.id
        if isinstance(db, dict):
            for u in db['users']:
                if u['_id'] == user['_id']:
                    u['stripe_customer_id'] = stripe_customer_id
                    break
        else:
            db.users.update_one({'_id': user['_id']}, {'$set': {'stripe_customer_id': stripe_customer_id}})
    else:
        stripe_customer_id = user['stripe_customer_id']

    try:
        checkout_session = stripe.checkout.Session.create(
            customer=stripe_customer_id,
            payment_method_types=['card'],
            line_items=[
                {
                    'price': STRIPE_PRICE_ID,
                    'quantity': 1,
                },
            ],
            mode='subscription',
            success_url=f"{STATIC_SITE_URL}/?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{STATIC_SITE_URL}/",
            metadata={
                'user_id': user['_id']
            }
        )
        return jsonify({'id': checkout_session.id})
    except Exception as e:
        logger.error(f"Stripe Checkout error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/stripe-webhook', methods=['POST'])
def stripe_webhook():
    """Handles webhooks from Stripe."""
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        # Invalid payload
        return 'Invalid payload', 400
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        return 'Invalid signature', 400

    # Handle the checkout.session.completed event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        user_id = session.get('metadata', {}).get('user_id')

        if user_id:
            logger.info(f"Stripe checkout session completed for user_id: {user_id}")
            # Update user's tier to premium
            if isinstance(db, dict):
                for u in db['users']:
                    if u['_id'] == user_id:
                        u['tier'] = 'premium'
                        logger.info(f"Upgraded user {user_id} to premium (in-memory).")
                        break
            else:
                db.users.update_one({'_id': user_id}, {'$set': {'tier': 'premium'}})
                logger.info(f"Upgraded user {user_id} to premium (MongoDB).")

    return 'Success', 200

@app.route('/affiliate/<product>')
def affiliate(product):
    """Track and redirect affiliate clicks"""
    links = {
        'jackery-explorer-240': 'https://amzn.to/3QZqX8Y',
        'lifestraw-filter': 'https://amzn.to/3QZqX8Y',
        '4patriots-food': 'https://4patriots.com/products/4week-food?drolid=0001',
        'alps-lynx': 'https://amzn.to/3QZqX8Y'
    }
    
    # Track the click with source
    source = request.args.get('source')
    track_affiliate_click(product, source)
    
    return redirect(links.get(product, '/gear'))

@app.route('/social/<platform>')
def social_redirect(platform):
    """Track and redirect social media clicks"""
    social_links = {
        'reddit': 'https://www.reddit.com/r/gorillacamping',
        'facebook': 'https://www.facebook.com/profile.php?id=61577334442896',
        'tiktok': 'https://www.tiktok.com/@gorillacamping'
    }
    return redirect(social_links.get(platform, '/'))

@app.route('/api/analytics/summary')
def api_analytics_summary():
    """Return basic analytics for the dashboard"""
    # Simple authentication
    api_key = request.args.get('api_key')
    if api_key != os.environ.get('ADMIN_API_KEY'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    if isinstance(db, dict):
        # Development data
        return jsonify({
            'affiliate_clicks': len(db['affiliate_clicks']),
            'subscribers': len(db['subscribers']),
            'ai_interactions': len(db['ai_usage']),
            'estimated_ai_cost': sum(item.get('estimated_cost', 0) for item in db['ai_usage'])
        })
    else:
        # MongoDB stats
        return jsonify({
            'affiliate_clicks': db.affiliate_clicks.count_documents({}),
            'subscribers': db.subscribers.count_documents({}),
            'ai_interactions': db.ai_usage.count_documents({}),
            'estimated_ai_cost': sum(item.get('estimated_cost', 0) 
                                    for item in db.ai_usage.find({}, {'estimated_cost': 1}))
        })

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_DEBUG', 'False') == 'True')
