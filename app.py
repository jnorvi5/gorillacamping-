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
    
    # Check if we're in a testing environment or if internet is not available
    if os.environ.get('TESTING') or os.environ.get('OFFLINE_MODE'):
        print("⚠️ Running in offline mode, ChromaDB disabled")
        knowledge_base = None
    else:
        try:
            hf_ef = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
            chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
            knowledge_base = chroma_client.get_collection(name=COLLECTION_NAME, embedding_function=hf_ef)
            print("✅ ChromaDB initialized")
        except Exception as e:
            print(f"⚠️ ChromaDB initialization failed: {e}")
            print("⚠️ Continuing without knowledge base")
            knowledge_base = None
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

# --- AZURE SERVICES SETUP ---
try:
    from azure_services import (
        azure_cosmos, azure_openai, azure_keyvault, azure_storage, azure_monitoring,
        get_config_value, get_database_client, get_ai_client
    )
    print("✅ Azure services module loaded")
except ImportError:
    print("⚠️ Azure services not available")
    azure_cosmos = azure_openai = azure_keyvault = azure_storage = azure_monitoring = None
    get_config_value = lambda key, default=None: os.environ.get(key, default)
    get_database_client = lambda: None
    get_ai_client = lambda: None

def ask_ai(user_query, context=""):
    """Ask AI using Azure OpenAI or Google Gemini fallback"""
    # Try Azure OpenAI first
    azure_ai = get_ai_client()
    if azure_ai and azure_ai.is_available():
        return azure_ai.generate_response(user_query, context)
    
    # Fallback to Google Gemini
    if genai:
        try:
            model = genai.GenerativeModel("gemini-pro")
            response = model.generate_content([{"role":"user", "parts":[context + "\n\n" + user_query]}])
            return response.text
        except Exception as e:
            print(f"❌ Gemini AI error: {e}")
    
    return "AI services are currently unavailable."

# Legacy function for backward compatibility
def ask_gemini(user_query, context=""):
    return ask_ai(user_query, context)

# --- DB SETUP ---
# Try Azure Cosmos DB first, then MongoDB fallback
azure_db = get_database_client()
if azure_db and azure_db.is_available():
    print("✅ Using Azure Cosmos DB")
    db = azure_db
    # Create a wrapper to make Cosmos DB compatible with existing MongoDB code
    class CosmosDBWrapper:
        def __init__(self, cosmos_client):
            self.cosmos = cosmos_client
            self.posts = self._get_container_wrapper('posts')
            self.ai_logs = self._get_container_wrapper('ai_logs')
            self.subscribers = self._get_container_wrapper('subscribers')
            
        def _get_container_wrapper(self, container_name):
            container = self.cosmos.get_container(container_name)
            return CosmosContainerWrapper(container) if container else None
    
    class CosmosContainerWrapper:
        def __init__(self, container):
            self.container = container
            
        def find(self, query=None):
            try:
                if query is None:
                    items = list(self.container.read_all_items())
                else:
                    # Convert MongoDB query to Cosmos DB SQL
                    items = list(self.container.query_items(
                        query="SELECT * FROM c",
                        enable_cross_partition_query=True
                    ))
                return CosmosQueryResult(items)
            except Exception as e:
                print(f"Cosmos DB query error: {e}")
                return CosmosQueryResult([])
                
        def find_one(self, query):
            try:
                # Simple implementation for basic queries
                if isinstance(query, dict) and 'slug' in query:
                    items = list(self.container.query_items(
                        query=f"SELECT * FROM c WHERE c.slug = '{query['slug']}'",
                        enable_cross_partition_query=True
                    ))
                    return items[0] if items else None
                elif isinstance(query, dict) and '_id' in query:
                    return self.container.read_item(item=str(query['_id']), partition_key=str(query['_id']))
                return None
            except Exception as e:
                print(f"Cosmos DB find_one error: {e}")
                return None
                
        def insert_one(self, document):
            try:
                # Add id if not present
                if 'id' not in document:
                    import uuid
                    document['id'] = str(uuid.uuid4())
                result = self.container.create_item(document)
                return type('Result', (), {'inserted_id': result['id']})()
            except Exception as e:
                print(f"Cosmos DB insert error: {e}")
                return None
                
        def sort(self, *args):
            return self
            
        def limit(self, count):
            return self
    
    class CosmosQueryResult:
        def __init__(self, items):
            self.items = items
            
        def sort(self, field, direction=-1):
            if field in ['created_at', 'updated_at']:
                reverse = direction == -1
                self.items.sort(key=lambda x: x.get(field, ''), reverse=reverse)
            return self
            
        def limit(self, count):
            self.items = self.items[:count]
            return self
            
        def __iter__(self):
            return iter(self.items)
            
        def __list__(self):
            return self.items
    
    db = CosmosDBWrapper(azure_db)
else:
    # MongoDB fallback
    try:
        mongodb_uri = get_config_value('MONGODB_URI') or get_config_value('MONGO_URI')
        if mongodb_uri:
            client = MongoClient(mongodb_uri)
            db = client.get_default_database()
            db.command('ping')
            print("✅ MongoDB connected successfully!")
        else:
            print("⚠️ No database URI found - running in demo mode")
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

@app.route('/gear')
def gear():
    gear_items = []
    # Add some hardcoded gear items if we don't have a DB
    if not db or not list(db.gear.find()):
        gear_items = [
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
        return jsonify({"success": False})
        
    # Use pre-paid Twilio credits from Student Pack
    try:
        requests.post('https://hooks.zapier.com/hooks/catch/YOUR_ZAPHOOK_ID/', 
                    json={"phone": phone})
        return jsonify({"success": True})
    except:
        return jsonify({"success": False})

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
        ai_response = ask_ai(user_query, context)
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
        try:
            if hasattr(db, 'downloads'):
                db.downloads.insert_one({
                    "infographic": name,
                    "timestamp": datetime.utcnow()
                })
        except Exception as e:
            print(f"Error logging download: {e}")
    try:
        return send_file(f'static/infographics/{name}.pdf')
    except:
        return redirect(url_for('home'))

# --- AZURE HEALTH CHECK ENDPOINTS ---

@app.route('/health')
def health():
    """Health check endpoint for Azure App Service"""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {}
    }
    
    # Check database connectivity
    if azure_cosmos and azure_cosmos.is_available():
        health_status["services"]["database"] = "azure_cosmos_db"
    elif db:
        health_status["services"]["database"] = "mongodb"
    else:
        health_status["services"]["database"] = "none"
    
    # Check AI service
    if azure_openai and azure_openai.is_available():
        health_status["services"]["ai"] = "azure_openai"
    elif genai:
        health_status["services"]["ai"] = "google_gemini"
    else:
        health_status["services"]["ai"] = "none"
    
    # Check other services
    health_status["services"]["knowledge_base"] = "available" if knowledge_base else "none"
    health_status["services"]["azure_keyvault"] = "available" if azure_keyvault and azure_keyvault.is_available() else "none"
    health_status["services"]["azure_storage"] = "available" if azure_storage and azure_storage.is_available() else "none"
    health_status["services"]["azure_monitoring"] = "available" if azure_monitoring and azure_monitoring.is_available() else "none"
    
    return jsonify(health_status)

@app.route('/azure/config')
def azure_config():
    """Azure configuration status endpoint"""
    config_status = {
        "azure_services_available": {
            "cosmos_db": azure_cosmos.is_available() if azure_cosmos else False,
            "openai": azure_openai.is_available() if azure_openai else False,
            "keyvault": azure_keyvault.is_available() if azure_keyvault else False,
            "storage": azure_storage.is_available() if azure_storage else False,
            "monitoring": azure_monitoring.is_available() if azure_monitoring else False
        },
        "environment_variables_configured": {
            "azure_cosmos_endpoint": bool(os.environ.get('AZURE_COSMOS_ENDPOINT')),
            "azure_openai_endpoint": bool(os.environ.get('AZURE_OPENAI_ENDPOINT')),
            "azure_keyvault_url": bool(os.environ.get('AZURE_KEYVAULT_URL')),
            "azure_storage_connection": bool(os.environ.get('AZURE_STORAGE_CONNECTION_STRING') or os.environ.get('AZURE_STORAGE_ACCOUNT_URL')),
            "application_insights": bool(os.environ.get('APPLICATIONINSIGHTS_CONNECTION_STRING'))
        }
    }
    return jsonify(config_status)

if __name__ == '__main__':
    app.run(debug=True)
