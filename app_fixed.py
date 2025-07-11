import os
import re
import random
import requests
from datetime import datetime, timedelta
from flask import Flask, request, render_template, jsonify, redirect, url_for, flash, session, Response, send_file
from pymongo import MongoClient
from urllib.parse import urlparse, parse_qs
import traceback

# --- FLASK SETUP ---
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'guerilla-camping-secret-2024')

# --- HANDLE OPTIONAL DEPENDENCIES ---
try:
    from flask_compress import Compress
    compress = Compress()
    compress.init_app(app)
    print("✅ Flask-Compress initialized")
except ImportError:
    print("⚠️ flask_compress not installed, continuing without compression")

try:
    import chromadb
    from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
    
    # --- CHROMADB + HUGGINGFACE EMBEDDINGS ---
    CHROMA_PATH = "./chroma_db"
    COLLECTION_NAME = "gorillacamping_kb"
    hf_ef = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
    knowledge_base = chroma_client.get_collection(name=COLLECTION_NAME, embedding_function=hf_ef)
    print("✅ ChromaDB initialized")
except ImportError:
    print("⚠️ ChromaDB not installed, continuing without knowledge base")
    knowledge_base = None

try:
    import google.generativeai as genai
    
    # --- GEMINI AI SETUP ---
    gemini_api_key = os.environ.get("GEMINI_API_KEY")
    if gemini_api_key:
        genai.configure(api_key=gemini_api_key)
        print("✅ Google Generative AI initialized")
    else:
        print("⚠️ GEMINI_API_KEY not set, AI features disabled")
except ImportError:
    print("⚠️ google.generativeai not installed, continuing without AI features")
    genai = None

def ask_gemini(user_query, context=""):
    if not genai:
        return "AI services are currently unavailable."
    
    try:
        model = genai.GenerativeModel("gemini-pro")
        response = model.generate_content([{"role":"user", "parts":[context + "\n\n" + user_query]}])
        return response.text
    except Exception as e:
        print(f"❌ Gemini API Error: {e}")
        return "Sorry, I'm having trouble processing your request right now. Please try again later."

# --- DB SETUP ---
try:
    mongodb_uri = os.environ.get('MONGODB_URI') or os.environ.get('MONGO_URI')
    if mongodb_uri:
        client = MongoClient(mongodb_uri)
        db = client.get_default_database()
        db.command('ping')
        print("✅ MongoDB connected successfully!")
    else:
        print("⚠️ No MongoDB URI found - running in demo mode")
        db = None
except Exception as e:
    print(f"❌ MongoDB connection failed: {e}")
    db = None

# --- ROUTES ---

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/blog')
def blog():
    posts = []
    if db:
        try:
            posts = list(db.posts.find().sort('created_at', -1))
        except Exception as e:
            print(f"Error fetching posts: {e}")
    return render_template('blog.html', posts=posts)

@app.route('/post/<slug>')
def post(slug):
    if db:
        post = db.posts.find_one({'slug': slug})
        if post:
            related_posts = list(db.posts.find({'_id': {'$ne': post['_id']}}).limit(3))
            return render_template('post.html', post=post, related_posts=related_posts)
    return redirect(url_for('blog'))

def get_default_gear_items():
    return [
        {
            'name': 'Jackery Explorer 240',
            'image': 'https://m.media-amazon.com/images/I/41XePYWYlAL._AC_US300_.jpg',
            'description': 'Perfect for keeping devices charged off-grid',
            'affiliate_id': 'jackery-explorer-240',
            'price': '$199.99',
            'old_price': '$299.99',
            'savings': 'Save $100',
            'rating': 5,
            'badges': ['HOT DEAL', 'BEST VALUE'],
            'specs': ['240Wh', '250W output', 'Multiple ports']
        },
        {
            'name': 'LifeStraw Personal Water Filter',
            'image': 'https://m.media-amazon.com/images/I/71SYsNwj7hL._AC_UL320_.jpg',
            'description': 'Essential survival gear that filters 99.9999% of waterborne bacteria',
            'affiliate_id': 'lifestraw-filter',
            'price': '$14.96',
            'old_price': '$19.95',
            'savings': 'Save 25%',
            'rating': 5,
            'badges': ['BESTSELLER'],
            'specs': ['1000L capacity', 'No chemicals', 'Compact']
        }
    ]

@app.route('/gear')
def gear():
    gear_items = []
    # Add some hardcoded gear items if we don't have a DB or the gear collection is empty
    if not db:
        gear_items = get_default_gear_items()
    else:
        try:
            # Check if gear collection has any items
            gear_count = db.gear.count_documents({})
            if gear_count == 0:
                gear_items = get_default_gear_items()
            else:
                gear_items = list(db.gear.find())
        except Exception as e:
            print(f"Error fetching gear items: {e}")
            gear_items = get_default_gear_items()
    
    return render_template('gear.html', gear_items=gear_items)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        subject = request.form.get('subject')
        message = request.form.get('message')
        
        if db:
            db.contacts.insert_one({
                'name': name,
                'email': email,
                'subject': subject,
                'message': message,
                'created_at': datetime.utcnow()
            })
        
        flash('Message received! We will get back to you soon.', 'success')
        return redirect(url_for('contact'))
    
    return render_template('contact.html')

@app.route('/affiliate/<product_id>')
def affiliate_redirect(product_id):
    affiliate_urls = {
        'jackery-explorer-240': 'https://www.amazon.com/Jackery-Portable-Explorer-Generator-Emergency/dp/B07D29QNMJ?&linkCode=ll1&tag=gorillcamping-20',
        'lifestraw-filter': 'https://www.amazon.com/LifeStraw-Personal-Filtering-Emergency-Preparedness/dp/B07VMSR74F?&linkCode=ll1&tag=gorillcamping-20'
    }
    
    url = affiliate_urls.get(product_id, 'https://www.amazon.com/?&linkCode=ll2&tag=gorillcamping-20')
    
    # Track click in database
    if db:
        db.affiliate_clicks.insert_one({
            'product_id': product_id,
            'timestamp': datetime.utcnow(),
            'user_agent': request.headers.get('User-Agent'),
            'referrer': request.referrer
        })
    
    return redirect(url)

@app.route('/social/<platform>')
def social_redirect(platform):
    social_urls = {
        'reddit': 'https://www.reddit.com/r/gorillacamping',
        'facebook': 'https://www.facebook.com/profile.php?id=61577334442896',
        'tiktok': 'https://www.tiktok.com/@gorillacamping'
    }
    
    url = social_urls.get(platform, 'https://www.reddit.com/r/gorillacamping')
    
    # Track social click
    if db:
        db.social_clicks.insert_one({
            'platform': platform,
            'timestamp': datetime.utcnow(),
            'user_agent': request.headers.get('User-Agent')
        })
    
    return redirect(url)

@app.route('/subscribe', methods=['POST'])
def subscribe():
    email = request.form.get('email')
    if not email:
        return jsonify({'success': False, 'message': 'Email is required'})
    
    # Store in our own DB
    if db:
        db.subscribers.update_one(
            {'email': email},
            {'$set': {'email': email, 'updated_at': datetime.utcnow()}, 
             '$setOnInsert': {'created_at': datetime.utcnow()}},
            upsert=True
        )
    
    return jsonify({'success': True, 'message': 'Subscribed successfully'})

@app.route('/guerilla-camping-bible')
def ebook():
    return render_template('ebook.html')

@app.route('/sms-signup', methods=['POST'])
def sms_signup():
    phone = request.form.get('phone')
    if not phone:
        return jsonify({"success": False, "message": "Phone number is required"})
        
    # TODO: Replace with your actual Zapier webhook URL
    zapier_webhook_url = os.environ.get('ZAPIER_WEBHOOK_URL')
    if not zapier_webhook_url:
        return jsonify({"success": False, "message": "SMS service not configured"})
        
    try:
        response = requests.post(zapier_webhook_url, 
                               json={"phone": phone}, 
                               timeout=10)
        if response.status_code == 200:
            return jsonify({"success": True, "message": "Successfully signed up for SMS updates"})
        else:
            return jsonify({"success": False, "message": "Failed to sign up for SMS updates"})
    except requests.RequestException as e:
        print(f"❌ SMS signup error: {e}")
        return jsonify({"success": False, "message": "SMS service temporarily unavailable"})

@app.route("/api/optimize", methods=['POST'])
def generative_ai_assistant():
    # Limit: 3 free queries per session unless Pro
    if not session.get("pro_user"):
        session['queries'] = session.get('queries', 0) + 1
        if session['queries'] > 3:
            return jsonify({"success": False, "message": "Upgrade to Pro for unlimited AI!"})
    
    data = request.json
    user_query = data.get("query", "I need some camping advice.")
    
    # 1. RAG: Retrieve context from your knowledge base using HuggingFace embeddings
    context = ""
    if knowledge_base:
        try:
            results = knowledge_base.query(query_texts=[user_query], n_results=5)
            context = "\n\n---\n\n".join(results['documents'][0]) if results['documents'] else ""
        except Exception as e:
            print(f"❌ Knowledge base error: {e}")
    
    # 2. Generate response
    try:
        ai_response = ask_gemini(user_query, context)
        # Optionally recommend gear based on AI answer
        gear_links = ""
        
        if db:
            db.ai_logs.insert_one({
                "question": user_query,
                "ai_response": ai_response,
                "timestamp": datetime.utcnow(),
                "user_agent": request.headers.get('User-Agent'),
                "ip_hash": hash(request.remote_addr) if request.remote_addr else None,
            })
        return jsonify({"success": True, "response": ai_response + gear_links})
    except Exception as e:
        print(f"❌ AI Error: {e}")
        return jsonify({"success": False, "message": "The AI brain is currently offline. Please try again later."})

@app.route('/tools')
def tools():
    # Create a tools comparison site using DO credit
    # Each tool has affiliate links
    return render_template('tools.html')

@app.route('/infographic/<name>')
def infographic(name):
    # Track downloads
    if db:
        db.downloads.insert_one({
            "infographic": name,
            "timestamp": datetime.utcnow()
        })
    try:
        return send_file(f'static/infographics/{name}.pdf')
    except Exception as e:
        print(f"❌ Error serving infographic: {e}")
        return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)
