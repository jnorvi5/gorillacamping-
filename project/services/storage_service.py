from pymongo import MongoClient
from datetime import datetime
from flask import request
from ..utils import generate_visitor_id

class StorageService:
    def __init__(self, app):
        self.app = app
        self.db = self._init_db()

    def _init_db(self):
        mongodb_uri = self.app.config['MONGODB_URI']
        if mongodb_uri:
            client = MongoClient(mongodb_uri)
            return client.get_default_database()
        else:
            # Fallback to in-memory storage for development
            self.app.logger.warning("No MongoDB URI found, falling back to in-memory storage.")
            return {
                'posts': [],
                'subscribers': [],
                'affiliate_clicks': [],
                'ai_usage': []
            }

    def track_ai_usage(self, prompt_tokens, completion_tokens, user_id=None, visitor_id=None):
        """Track AI usage for cost monitoring"""
        if isinstance(self.db, dict):
            # In-memory storage
            self.db['ai_usage'].append({
                'prompt_tokens': prompt_tokens,
                'completion_tokens': completion_tokens,
                'user_id': user_id,
                'visitor_id': visitor_id,
                'timestamp': datetime.utcnow().isoformat(),
                'estimated_cost': (prompt_tokens * 0.00001) + (completion_tokens * 0.00003)
            })
        else:
            # MongoDB storage
            self.db.ai_usage.insert_one({
                'prompt_tokens': prompt_tokens,
                'completion_tokens': completion_tokens,
                'user_id': user_id,
                'visitor_id': visitor_id,
                'timestamp': datetime.utcnow(),
                'estimated_cost': (prompt_tokens * 0.00001) + (completion_tokens * 0.00003)
            })

    def track_affiliate_click(self, product_id, source=None):
        """Enhanced tracking for affiliate clicks with source attribution"""
        if isinstance(self.db, dict):
            # In-memory tracking for development
            self.db['affiliate_clicks'].append({
                'product_id': product_id,
                'timestamp': datetime.utcnow().isoformat(),
                'visitor_id': request.cookies.get('visitor_id', generate_visitor_id()),
                'referrer': request.referrer,
                'user_agent': request.user_agent.string,
                'source': source or 'direct',
                'chat_recommendation': source == 'chat',
            })
        else:
            # MongoDB tracking
            self.db.affiliate_clicks.insert_one({
                'product_id': product_id,
                'timestamp': datetime.utcnow(),
                'visitor_id': request.cookies.get('visitor_id', generate_visitor_id()),
                'referrer': request.referrer,
                'user_agent': request.user_agent.string,
                'source': source or 'direct',
                'chat_recommendation': source == 'chat',
            })

    def get_blog_posts(self):
        """Return all blog posts as JSON"""
        if isinstance(self.db, dict):
            # Fallback to sample data for development
            return [
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
            posts = list(self.db.posts.find({"status": "published"}))
            for post in posts:
                post['_id'] = str(post['_id'])
                post['created_at'] = post['created_at'].strftime('%Y-%m-%d')
            return posts

    def get_blog_post_by_slug(self, slug):
        """Return a single post by slug"""
        if isinstance(self.db, dict):
            # Fallback to sample data for development
            return {
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
            post = self.db.posts.find_one({'slug': slug, 'status': 'published'})
            if post:
                post['_id'] = str(post['_id'])
                post['created_at'] = post['created_at'].strftime('%Y-%m-%d')
            return post

    def add_subscriber(self, email, source):
        """Add email to subscribers"""
        if isinstance(self.db, dict):
            # In-memory tracking for development
            existing = False
            for sub in self.db['subscribers']:
                if sub.get('email') == email:
                    existing = True
                    break

            if existing:
                return False, "Already subscribed"

            self.db['subscribers'].append({
                'email': email,
                'source': source,
                'timestamp': datetime.utcnow().isoformat(),
                'visitor_id': request.cookies.get('visitor_id', generate_visitor_id()),
                'active': True
            })
            return True, "Subscribed"
        else:
            # MongoDB
            existing = self.db.subscribers.find_one({'email': email})
            if existing:
                return False, "Already subscribed"

            self.db.subscribers.insert_one({
                'email': email,
                'source': source,
                'timestamp': datetime.utcnow(),
                'visitor_id': request.cookies.get('visitor_id', generate_visitor_id()),
                'active': True
            })
            return True, "Subscribed"

    def get_analytics_summary(self):
        """Return basic analytics for the dashboard"""
        if isinstance(self.db, dict):
            # Development data
            return {
                'affiliate_clicks': len(self.db['affiliate_clicks']),
                'subscribers': len(self.db['subscribers']),
                'ai_interactions': len(self.db['ai_usage']),
                'estimated_ai_cost': sum(item.get('estimated_cost', 0) for item in self.db['ai_usage'])
            }
        else:
            # MongoDB stats
            return {
                'affiliate_clicks': self.db.affiliate_clicks.count_documents({}),
                'subscribers': self.db.subscribers.count_documents({}),
                'ai_interactions': self.db.ai_usage.count_documents({}),
                'estimated_ai_cost': sum(item.get('estimated_cost', 0)
                                        for item in self.db.ai_usage.find({}, {'estimated_cost': 1}))
            }
