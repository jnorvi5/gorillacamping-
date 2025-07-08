import os
import re
import random
import requests
import uuid
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

# --- OPENAI SETUP ---
openai_client = None
try:
    import openai
    
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    if openai_api_key:
        openai_client = openai.OpenAI(api_key=openai_api_key)
        print("✅ OpenAI initialized")
    else:
        print("⚠️ OPENAI_API_KEY not set, Pro AI features disabled")
except ImportError:
    print("⚠️ openai not installed, continuing without OpenAI features")

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

def ask_openai(user_query, context="", model="gpt-3.5-turbo"):
    """Ask OpenAI for Pro users with better model options"""
    if not openai_client:
        return "Pro AI services are currently unavailable."
    
    try:
        messages = [
            {"role": "system", "content": context or "You are Guerilla the Gorilla, an expert camping advisor who helps with off-grid living, gear optimization, and making money while camping."},
            {"role": "user", "content": user_query}
        ]
        
        response = openai_client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=1000,
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"❌ OpenAI API Error: {e}")
        return "Sorry, I'm having trouble processing your request right now. Please try again later."

def calculate_camping_score(user_preferences):
    """Calculate optimized camping setup score based on user preferences"""
    score = 0
    recommendations = []
    
    # Setup type scoring
    setup_type = user_preferences.get('setup_type', '')
    if setup_type == 'van':
        score += 20
        recommendations.append("Van life offers great mobility and stealth camping options")
    elif setup_type == 'tent':
        score += 15
        recommendations.append("Tent camping is budget-friendly and offers flexibility")
    elif setup_type == 'fifth_wheel':
        score += 25
        recommendations.append("Fifth wheels provide maximum comfort and storage")
    elif setup_type == 'rv':
        score += 22
        recommendations.append("RVs offer good balance of comfort and mobility")
    
    # Power setup scoring
    power_type = user_preferences.get('power_type', '')
    available_amps = user_preferences.get('available_amps', 0)
    
    if power_type == 'solar':
        score += 15
        recommendations.append("Solar power is environmentally friendly and cost-effective long-term")
    elif power_type == 'generator':
        score += 10
        recommendations.append("Generators provide reliable power but require fuel")
    elif power_type == 'shore_power':
        score += 8
        recommendations.append("Shore power is convenient at established campgrounds")
    
    if available_amps >= 50:
        score += 15
        recommendations.append("High amp capacity allows for full electrical usage")
    elif available_amps >= 30:
        score += 12
        recommendations.append("30 amp service covers most camping needs")
    elif available_amps >= 15:
        score += 8
        recommendations.append("15 amp service requires careful power management")
    
    # Location preferences
    location_type = user_preferences.get('location_type', '')
    if location_type == 'boondocking':
        score += 20
        recommendations.append("Boondocking offers freedom and low costs but requires self-sufficiency")
    elif location_type == 'campground':
        score += 12
        recommendations.append("Campgrounds provide amenities and security")
    elif location_type == 'mixed':
        score += 18
        recommendations.append("Mixed camping provides flexibility and variety")
    
    # Budget considerations
    budget_range = user_preferences.get('budget_range', '')
    if budget_range == 'low':
        score += 10
        recommendations.append("Budget camping requires smart gear choices and resourcefulness")
    elif budget_range == 'medium':
        score += 15
        recommendations.append("Medium budget allows for quality essential gear")
    elif budget_range == 'high':
        score += 12
        recommendations.append("Higher budget enables premium gear and comfort features")
    
    return {
        'score': min(score, 100),  # Cap at 100
        'recommendations': recommendations,
        'optimization_tips': generate_optimization_tips(user_preferences)
    }

def generate_optimization_tips(preferences):
    """Generate specific optimization tips based on user setup"""
    tips = []
    
    setup_type = preferences.get('setup_type', '')
    power_type = preferences.get('power_type', '')
    budget = preferences.get('budget_range', '')
    
    # Power optimization tips
    if power_type == 'solar':
        tips.append("Position solar panels for maximum sun exposure (south-facing, 30-degree tilt)")
        tips.append("Consider battery bank expansion for cloudy days")
    elif power_type == 'generator':
        tips.append("Run generator during peak efficiency hours (avoid early morning/late evening)")
        tips.append("Invest in a fuel-efficient inverter generator for quiet operation")
    
    # Setup-specific tips
    if setup_type == 'van':
        tips.append("Maximize vertical storage space with modular systems")
        tips.append("Install roof fans for better ventilation and temperature control")
    elif setup_type == 'tent':
        tips.append("Choose campsites with natural windbreaks and level ground")
        tips.append("Invest in a quality sleeping system for comfort and warmth")
    
    # Budget-conscious tips
    if budget == 'low':
        tips.append("Buy used gear from Facebook Marketplace and REI Co-op")
        tips.append("DIY modifications can save 50-70% on custom solutions")
    
    return tips

def get_bluetooth_device_recommendations(setup_type, power_type):
    """Recommend Bluetooth-enabled camping devices based on setup"""
    recommendations = []
    
    # Universal recommendations
    recommendations.append({
        "device": "Jackery Power Station with App",
        "reason": "Monitor battery levels and charging status remotely",
        "compatibility": "All setups"
    })
    
    recommendations.append({
        "device": "Bluetooth Thermometer/Hygrometer",
        "reason": "Track temperature and humidity for comfort optimization",
        "compatibility": "All setups"
    })
    
    # Setup-specific recommendations
    if setup_type in ['van', 'rv', 'fifth_wheel']:
        recommendations.append({
            "device": "Victron Smart Solar Charge Controller",
            "reason": "Monitor solar charging efficiency via smartphone app",
            "compatibility": "Solar setups"
        })
        
        recommendations.append({
            "device": "Bluetooth Tank Level Monitors",
            "reason": "Track water and waste tank levels without manual checking",
            "compatibility": "RVs and vans with tanks"
        })
    
    if power_type == 'generator':
        recommendations.append({
            "device": "Honda EU2200i with Bluetooth",
            "reason": "Monitor runtime, maintenance needs, and fuel consumption",
            "compatibility": "Generator users"
        })
    
    return recommendations

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
    is_pro_user = session.get("pro_user", False)
    
    if not is_pro_user:
        session['queries'] = session.get('queries', 0) + 1
        if session['queries'] > 3:
            return jsonify({"success": False, "message": "Upgrade to Pro for unlimited AI and advanced optimization!"})
    
    data = request.json
    user_query = data.get("query", "I need some camping advice.")
    user_preferences = data.get("preferences", {})
    
    # 1. RAG: Retrieve context from your knowledge base using HuggingFace embeddings
    context = ""
    if knowledge_base:
        try:
            results = knowledge_base.query(query_texts=[user_query], n_results=5)
            context = "\n\n---\n\n".join(results['documents'][0]) if results['documents'] else ""
        except Exception as e:
            print(f"❌ Knowledge base error: {e}")
    
    # 2. Enhanced context for camping optimization
    if user_preferences:
        camping_analysis = calculate_camping_score(user_preferences)
        context += f"\n\nUser's Camping Setup Analysis:\n"
        context += f"Optimization Score: {camping_analysis['score']}/100\n"
        context += f"Recommendations: {'; '.join(camping_analysis['recommendations'])}\n"
        context += f"Optimization Tips: {'; '.join(camping_analysis['optimization_tips'])}\n"
        
        # Add Bluetooth device recommendations
        bluetooth_devices = get_bluetooth_device_recommendations(
            user_preferences.get('setup_type', ''),
            user_preferences.get('power_type', '')
        )
        if bluetooth_devices:
            context += f"\nRecommended Bluetooth Devices:\n"
            for device in bluetooth_devices[:3]:  # Limit to top 3
                context += f"- {device['device']}: {device['reason']}\n"
    
    # 3. Generate response using appropriate AI model
    try:
        if is_pro_user and openai_client:
            # Pro users get OpenAI with better context understanding
            enhanced_context = context + "\n\nYou are Guerilla the Gorilla, an expert camping advisor. Provide detailed, actionable advice with specific gear recommendations. Be conversational but authoritative."
            ai_response = ask_openai(user_query, enhanced_context, "gpt-3.5-turbo")
        else:
            # Free users get Gemini
            ai_response = ask_gemini(user_query, context)
        
        # 4. Add camping score and recommendations to response if preferences provided
        additional_data = {}
        if user_preferences:
            camping_analysis = calculate_camping_score(user_preferences)
            additional_data = {
                "camping_score": camping_analysis['score'],
                "recommendations": camping_analysis['recommendations'],
                "optimization_tips": camping_analysis['optimization_tips'],
                "bluetooth_devices": get_bluetooth_device_recommendations(
                    user_preferences.get('setup_type', ''),
                    user_preferences.get('power_type', '')
                )
            }
        
        # 5. Log the interaction
        if db:
            db.ai_logs.insert_one({
                "question": user_query,
                "ai_response": ai_response,
                "user_preferences": user_preferences,
                "is_pro_user": is_pro_user,
                "ai_model": "openai" if is_pro_user and openai_client else "gemini",
                "timestamp": datetime.utcnow(),
                "user_agent": request.headers.get('User-Agent'),
                "ip_hash": hash(request.remote_addr) if request.remote_addr else None,
            })
        
        response_data = {
            "success": True,
            "response": ai_response,
            "ai_model": "OpenAI GPT-3.5" if is_pro_user and openai_client else "Google Gemini",
            **additional_data
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        print(f"❌ AI Error: {e}")
        return jsonify({"success": False, "message": "The AI brain is currently offline. Please try again later."})

@app.route('/api/preferences', methods=['POST'])
def save_user_preferences():
    """Save user camping preferences for personalized recommendations"""
    data = request.json
    user_id = session.get('user_id', str(uuid.uuid4())[:8])
    session['user_id'] = user_id
    
    preferences = {
        'user_id': user_id,
        'setup_type': data.get('setup_type', ''),
        'power_type': data.get('power_type', ''),
        'available_amps': int(data.get('available_amps', 0)),
        'location_type': data.get('location_type', ''),
        'budget_range': data.get('budget_range', ''),
        'experience_level': data.get('experience_level', 'beginner'),
        'primary_activities': data.get('primary_activities', []),
        'bluetooth_devices': data.get('bluetooth_devices', []),
        'timestamp': datetime.utcnow()
    }
    
    if db:
        try:
            # Update or insert preferences
            db.user_preferences.update_one(
                {'user_id': user_id},
                {'$set': preferences},
                upsert=True
            )
        except Exception as e:
            print(f"Error saving preferences: {e}")
    
    # Calculate initial score
    camping_analysis = calculate_camping_score(preferences)
    
    return jsonify({
        "success": True,
        "message": "Preferences saved successfully!",
        "camping_score": camping_analysis['score'],
        "recommendations": camping_analysis['recommendations']
    })

@app.route('/api/preferences', methods=['GET'])
def get_user_preferences():
    """Get saved user preferences"""
    user_id = session.get('user_id')
    
    if not user_id or not db:
        return jsonify({"success": False, "message": "No preferences found"})
    
    try:
        preferences = db.user_preferences.find_one({'user_id': user_id})
        if preferences:
            # Remove MongoDB _id field
            preferences.pop('_id', None)
            return jsonify({"success": True, "preferences": preferences})
        else:
            return jsonify({"success": False, "message": "No preferences found"})
    except Exception as e:
        print(f"Error fetching preferences: {e}")
        return jsonify({"success": False, "message": "Error fetching preferences"})

@app.route('/api/pro-upgrade', methods=['POST'])
def pro_upgrade():
    """Simulate Pro upgrade (in real app, integrate with payment processor)"""
    data = request.json
    upgrade_code = data.get('upgrade_code', '')
    
    # Simple demo upgrade codes
    valid_codes = ['GORILLA2025', 'PROCAMP', 'DEMO123']
    
    if upgrade_code in valid_codes:
        session['pro_user'] = True
        session['queries'] = 0  # Reset query count
        
        if db:
            user_id = session.get('user_id', str(uuid.uuid4())[:8])
            session['user_id'] = user_id
            
            db.pro_upgrades.insert_one({
                'user_id': user_id,
                'upgrade_code': upgrade_code,
                'timestamp': datetime.utcnow(),
                'ip_hash': hash(request.remote_addr) if request.remote_addr else None
            })
        
        return jsonify({
            "success": True,
            "message": "Welcome to Pro! You now have unlimited AI queries and access to OpenAI models.",
            "features": [
                "Unlimited AI consultations",
                "Advanced OpenAI GPT models",
                "Comprehensive camping optimization",
                "Bluetooth device integration",
                "Priority support"
            ]
        })
    else:
        return jsonify({"success": False, "message": "Invalid upgrade code"})

@app.route('/api/bluetooth-scan', methods=['POST'])
def bluetooth_scan_simulation():
    """Simulate Bluetooth device scanning for camping gear"""
    # In a real implementation, this would interface with actual Bluetooth scanning
    # For demo purposes, we'll return simulated discovered devices
    
    simulated_devices = [
        {
            "name": "Jackery Explorer 1000",
            "type": "Power Station",
            "battery_level": 78,
            "status": "Charging",
            "mac_address": "XX:XX:XX:XX:XX:01"
        },
        {
            "name": "Acurite Weather Station",
            "type": "Weather Monitor",
            "temperature": 72.5,
            "humidity": 45,
            "mac_address": "XX:XX:XX:XX:XX:02"
        },
        {
            "name": "TPMS Sensor",
            "type": "Tire Pressure",
            "pressure_psi": 32,
            "temperature": 68,
            "mac_address": "XX:XX:XX:XX:XX:03"
        }
    ]
    
    return jsonify({
        "success": True,
        "devices_found": len(simulated_devices),
        "devices": simulated_devices,
        "message": "Bluetooth scan complete. Connect devices through their respective apps for full integration."
    })

@app.route('/tools')
def tools():
    # Create a tools comparison site using DO credit
    # Each tool has affiliate links
    return render_template('tools.html')

@app.route('/optimizer')
def camping_optimizer():
    """Advanced camping setup optimizer with AI and Bluetooth integration"""
    return render_template('camping_optimizer.html')

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
