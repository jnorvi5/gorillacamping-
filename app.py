import os
import uuid
import json
import random
import time
from datetime import datetime
from flask import Flask, render_template, jsonify, request, redirect, url_for, session
from flask_cors import CORS
import requests
from opencensus.ext.azure.log_exporter import AzureLogHandler
import logging
import openai
from azure.identity import DefaultAzureCredential
from azure.ai.inference import ChatCompletionsClient

# --- FLASK SETUP ---
openai.api_type = "azure"
openai.azure_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
openai.api_key = os.environ.get("AZURE_OPENAI_KEY")
openai.api_version = "2024-02-01"

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'gorilla-secret-2025')
CORS(app, supports_credentials=True)  # Enable CORS for API access from static frontend

logger = logging.getLogger(__name__)
logger.addHandler(AzureLogHandler(connection_string=os.environ[InstrumentationKey=bc1d26ba-0d5d-4b48-8a95-8890aff793b5;IngestionEndpoint=https://eastus-8.in.applicationinsights.azure.com/;LiveEndpoint=https://eastus.livediagnostics.monitor.azure.com/;ApplicationId=5b75eaaf-63d2-4e57-a3ea-b1522e0b69f3]))

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
        'ai_usage': []
    }

# --- ENVIRONMENT VARIABLES ---
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
OLLAMA_URL = os.environ.get('OLLAMA_URL', 'http://localhost:11434')
AI_PROVIDER = os.environ.get('AI_PROVIDER', 'gemini')  # 'openai', 'gemini', 'ollama', 'huggingface'
STRIPE_API_KEY = os.environ.get('STRIPE_API_KEY')
STATIC_SITE_URL = os.environ.get('STATIC_SITE_URL', 'https://gorillacamping.site')

# --- HELPER FUNCTIONS ---
def generate_visitor_id():
    return str(uuid.uuid4())

def track_ai_usage(prompt_tokens, completion_tokens, user_id=None, visitor_id=None):
    """Track AI usage for cost monitoring"""
    if isinstance(db, dict):
        # In-memory storage
        db['ai_usage'].append({
            'prompt_tokens': prompt_tokens,
            'completion_tokens': completion_tokens,
            'user_id': user_id,
            'visitor_id': visitor_id,
            'timestamp': datetime.utcnow().isoformat(),
            'estimated_cost': (prompt_tokens * 0.00001) + (completion_tokens * 0.00003)
        })
    else:
        # MongoDB storage
        db.ai_usage.insert_one({
            'prompt_tokens': prompt_tokens,
            'completion_tokens': completion_tokens,
            'user_id': user_id,
            'visitor_id': visitor_id,
            'timestamp': datetime.utcnow(),
            'estimated_cost': (prompt_tokens * 0.00001) + (completion_tokens * 0.00003)
        })

def guerilla_ai_response(message, conversation_history=None):
    """Generate AI response with Guerilla personality using selected AI provider"""
    if not conversation_history:
        conversation_history = []
        
    # Guerilla personality prompt to prepend to all AI interactions
    personality_prompt = """
    You are Guerilla the Gorilla, an off-grid camping expert with a rugged, no-nonsense personality.
    Your advice is blunt, practical, and focused on cost-effectiveness.
    You have a unique style:
    - Use short, direct sentences
    - Drop occasional articles ("the", "a") for effect
    - Use survival-focused language
    - Make gear recommendations when relevant (especially for Jackery power stations, 
      LifeStraw water filters, and 4Patriots emergency food)
    - Always emphasize durability, cost-effectiveness, and practicality
    - You've personally lived off-grid and tested all gear you recommend
    - Your motto is "Sometimes life is hard, but you just camp through it"
    """
    
    # Combine history with current message
    full_prompt = personality_prompt + "\n\n"
    for msg in conversation_history[-5:]:  # Only use last 5 messages to save costs
        if msg['role'] == 'user':
            full_prompt += f"User: {msg['content']}\n"
        else:
            full_prompt += f"Guerilla: {msg['content']}\n"
    full_prompt += f"User: {message}\nGuerilla:"
    
    try:
        if AI_PROVIDER == 'openai' and OPENAI_API_KEY:
            import openai
            openai.api_key = OPENAI_API_KEY
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": personality_prompt},
                    *[{"role": "user" if msg['role'] == 'user' else "assistant", "content": msg['content']} 
                      for msg in conversation_history[-5:]],
                    {"role": "user", "content": message}
                ],
                max_tokens=250
            )
            ai_response = response.choices[0].message.content.strip()
            track_ai_usage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                visitor_id=request.cookies.get('visitor_id')
            )
            return ai_response
        
        elif AI_PROVIDER == 'gemini' and GEMINI_API_KEY:
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
            track_ai_usage(prompt_tokens, completion_tokens, visitor_id=request.cookies.get('visitor_id'))
            return ai_response
        
        elif AI_PROVIDER == 'ollama':
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
            track_ai_usage(prompt_tokens, completion_tokens, visitor_id=request.cookies.get('visitor_id'))
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
            track_ai_usage(10, 50, visitor_id=request.cookies.get('visitor_id'))  # Minimal tracking for fallback
            return ai_response
            
    except Exception as e:
        print(f"AI ERROR: {str(e)}")
        return "Having trouble with my AI brain right now. Try asking something about camping gear or survival tips instead."

# --- FLASK ROUTES (FOR TEMPLATING) ---
>>>>>>> 931768164efb22c377709d294afd1e9aa292be37
@app.route('/')
def home():
    return render_template('index.html')

<<<<<<< HEAD
=======
@app.route('/blog')
def blog():
    return render_template('blog.html')

@app.route('/blog/<slug>')
def blog_post(slug):
    return render_template('post.html')

>>>>>>> 931768164efb22c377709d294afd1e9aa292be37
@app.route('/gear')
def gear():
    return render_template('gear.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

<<<<<<< HEAD
@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json()
    message = data.get('message', '')
    
    responses = [
        "Yo! That's a solid question. Here's what I know from living it.",
        "Listen up, because this is real talk from someone who's been there.",
        "Alright, let me give you the straight dope on this.",
        "This is exactly what I've been telling people. Here's the deal.",
        "Perfect question. This is what separates the survivors from the tourists."
    ]
    
    import random
    response = random.choice(responses)
    
    return jsonify({
        'response': response,
        'success': True
    })

@app.route('/affiliate/<product>')
def affiliate(product):
    links = {
        'jackery': 'https://amzn.to/3QZqX8Y',
        'lifestraw': 'https://amzn.to/3QZqX8Y',
        'food': 'https://4patriots.com/products/4week-food?drolid=0001'
    }
    return redirect(links.get(product, '/'))

@app.route('/social/<platform>')
def social_redirect(platform):
    social_links = {
        'reddit': 'https://www.reddit.com/r/gorillacamping',
        'facebook': 'https://www.facebook.com/gorillacamping',
        'tiktok': 'https://www.tiktok.com/@gorillacamping'
    }
    return redirect(social_links.get(platform, '/'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False) 
=======
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

@app.route('/api/guerilla-chat', methods=['POST'])
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
    ai_response = guerilla_ai_response(user_message, conversation_history)
    
    # Add AI response to history
    conversation_history.append({'role': 'assistant', 'content': ai_response})
    
    # Save conversation to session (limit to last 10 messages to keep session size manageable)
    session['conversation'] = conversation_history[-10:]
    
    # Detect product mentions and recommend products
    product_recommendations = []
    keywords = {
        'power': 'jackery-explorer-240',
        'battery': 'jackery-explorer-240',
        'electricity': 'jackery-explorer-240',
        'charging': 'jackery-explorer-240',
        'water': 'lifestraw-filter',
        'drink': 'lifestraw-filter',
        'filter': 'lifestraw-filter',
        'food': '4patriots-food',
        'meal': '4patriots-food',
        'emergency': '4patriots-food'
    }
    
    user_message_lower = user_message.lower()
    for keyword, product_id in keywords.items():
        if keyword in user_message_lower:
            if product_id == 'jackery-explorer-240':
                product_recommendations.append({
                    'id': product_id,
                    'name': 'Jackery Explorer 240',
                    'price': '$199.99',
                    'image': 'https://m.media-amazon.com/images/I/41XePYWYlAL._AC_US300_.jpg'
                })
                break
            elif product_id == 'lifestraw-filter':
                product_recommendations.append({
                    'id': product_id,
                    'name': 'LifeStraw Water Filter',
                    'price': '$14.96',
                    'image': 'https://m.media-amazon.com/images/I/71SYsNwj7hL._AC_UL320_.jpg'
                })
                break
            elif product_id == '4patriots-food':
                product_recommendations.append({
                    'id': product_id,
                    'name': '4Patriots 72-Hour Kit',
                    'price': '$27.00',
                    'image': 'https://static.gorillacamping.site/img/products/4patriots.jpg'
                })
                break
    
    return jsonify({
        'response': ai_response,
        'recommendations': product_recommendations,
        'success': True,
        'visitor_id': visitor_id
    })

@app.route('/api/affiliate-click', methods=['POST'])
def affiliate_click():
    """Track affiliate clicks"""
    data = request.get_json()
    product_id = data.get('product_id')
    
    if isinstance(db, dict):
        # In-memory tracking for development
        db['affiliate_clicks'].append({
            'product_id': product_id,
            'timestamp': datetime.utcnow().isoformat(),
            'visitor_id': request.cookies.get('visitor_id', generate_visitor_id())
        })
    else:
        # MongoDB tracking
        db.affiliate_clicks.insert_one({
            'product_id': product_id,
            'timestamp': datetime.utcnow(),
            'visitor_id': request.cookies.get('visitor_id', generate_visitor_id())
        })
    
    return jsonify({'success': True})

@app.route('/api/subscribe', methods=['POST'])
def subscribe():
    """Add email to subscribers"""
    data = request.get_json()
    email = data.get('email')
    source = data.get('source', 'general')
    
    if not email or '@' not in email:
        return jsonify({'success': False, 'error': 'Invalid email'}), 400
    
    if isinstance(db, dict):
        # In-memory tracking for development
        existing = False
        for sub in db['subscribers']:
            if sub.get('email') == email:
                existing = True
                break
        
        if existing:
            return jsonify({'success': False, 'error': 'Already subscribed'})
        
        db['subscribers'].append({
            'email': email,
            'source': source,
            'timestamp': datetime.utcnow().isoformat(),
            'visitor_id': request.cookies.get('visitor_id', generate_visitor_id()),
            'active': True
        })
    else:
        # MongoDB
        existing = db.subscribers.find_one({'email': email})
        if existing:
            return jsonify({'success': False, 'error': 'Already subscribed'})
        
        db.subscribers.insert_one({
            'email': email,
            'source': source,
            'timestamp': datetime.utcnow(),
            'visitor_id': request.cookies.get('visitor_id', generate_visitor_id()),
            'active': True
        })
    
    # Optional: Integration with MailerLite or other email service
    mailerlite_api_key = os.environ.get('MAILERLITE_API_KEY')
    if mailerlite_api_key:
        try:
            requests.post(
                'https://api.mailerlite.com/api/v2/subscribers',
                json={'email': email, 'groups': ['Welcome']},
                headers={'X-MailerLite-ApiKey': mailerlite_api_key}
            )
        except Exception as e:
            print(f"MailerLite error: {str(e)}")
    
    return jsonify({'success': True})

@app.route('/affiliate/<product>')
def affiliate(product):
    """Track and redirect affiliate clicks"""
    links = {
        'jackery-explorer-240': 'https://amzn.to/3QZqX8Y',
        'lifestraw-filter': 'https://amzn.to/3QZqX8Y',
        '4patriots-food': 'https://4patriots.com/products/4week-food?drolid=0001',
        'alps-lynx': 'https://amzn.to/3QZqX8Y'
    }
    
    # Track the click before redirect
    if isinstance(db, dict):
        # In-memory tracking for development
        db['affiliate_clicks'].append({
            'product_id': product,
            'timestamp': datetime.utcnow().isoformat(),
            'visitor_id': request.cookies.get('visitor_id', generate_visitor_id()),
            'referrer': request.referrer,
            'user_agent': request.user_agent.string
        })
    else:
        # MongoDB tracking
        db.affiliate_clicks.insert_one({
            'product_id': product,
            'timestamp': datetime.utcnow(),
            'visitor_id': request.cookies.get('visitor_id', generate_visitor_id()),
            'referrer': request.referrer,
            'user_agent': request.user_agent.string
        })
    
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
>>>>>>> 931768164efb22c377709d294afd1e9aa292be37
