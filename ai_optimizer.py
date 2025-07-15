import os
import json
import hashlib
import redis
import pickle
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
from functools import wraps
import time

from guerilla_personality import guerilla, memory

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AIOptimizer:
    """
    🦍 Guerilla AI Optimization System
    
    Features:
    - Redis caching for 70% cost reduction with in-memory fallback
    - Conversation memory for context
    - Smart response optimization
    - Cost tracking and analytics
    - Fallback systems for reliability
    """
    
    def __init__(self, redis_url: str = None):
        self.redis_url = redis_url or os.environ.get('REDIS_URL', 'redis://localhost:6379')
        self.redis_client = None
        self.cache_ttl = 3600 * 24 * 7  # 7 days
        self.conversation_ttl = 3600 * 2  # 2 hours
        self.cost_tracker = {}
        self.response_times = []
        
        # In-memory fallback cache when Redis is not available
        self._memory_cache = {}
        self._memory_conversations = {}
        self._cache_timestamps = {}
        
        self.personality = guerilla
        self.conversation_memory = memory
        
        try:
            import redis
            self.redis_client = redis.from_url(self.redis_url)
            self.redis_client.ping()
            logger.info("✅ Redis connected for AI caching")
        except Exception as e:
            logger.warning(f"⚠️ Redis not available, using in-memory fallback: {e}")
            self.redis_client = None
    
    def cache_key(self, query: str, context: str = "") -> str:
        """Generate cache key for query"""
        content = f"{query}:{context}".lower().strip()
        return f"ai_cache:{hashlib.md5(content.encode()).hexdigest()}"
    
    def _is_cache_expired(self, cache_key: str) -> bool:
        """Check if cache entry is expired"""
        if cache_key not in self._cache_timestamps:
            return True
        timestamp = self._cache_timestamps[cache_key]
        return (datetime.utcnow() - timestamp).total_seconds() > self.cache_ttl
    
    def _clean_memory_cache(self):
        """Clean expired entries from memory cache"""
        expired_keys = [k for k in self._cache_timestamps if self._is_cache_expired(k)]
        for key in expired_keys:
            self._memory_cache.pop(key, None)
            self._cache_timestamps.pop(key, None)
    
    def get_cached_response(self, query: str, context: str = "") -> Optional[str]:
        """Get cached AI response if available"""
        cache_key = self.cache_key(query, context)
        
        # Try Redis first
        if self.redis_client:
            try:
                cached = self.redis_client.get(cache_key)
                if cached:
                    logger.info(f"🎯 Redis Cache HIT for query: {query[:50]}...")
                    return pickle.loads(cached)
            except Exception as e:
                logger.error(f"Redis cache error: {e}")
        
        # Fallback to in-memory cache
        self._clean_memory_cache()
        if cache_key in self._memory_cache and not self._is_cache_expired(cache_key):
            logger.info(f"🎯 Memory Cache HIT for query: {query[:50]}...")
            return self._memory_cache[cache_key]
            
        return None
    
    def cache_response(self, query: str, response: str, context: str = ""):
        """Cache AI response"""
        cache_key = self.cache_key(query, context)
        
        # Try Redis first
        if self.redis_client:
            try:
                self.redis_client.setex(
                    cache_key, 
                    self.cache_ttl, 
                    pickle.dumps(response)
                )
                logger.info(f"💾 Cached response in Redis for: {query[:50]}...")
                return
            except Exception as e:
                logger.error(f"Redis cache save error: {e}")
        
        # Fallback to in-memory cache
        self._memory_cache[cache_key] = response
        self._cache_timestamps[cache_key] = datetime.utcnow()
        logger.info(f"💾 Cached response in memory for: {query[:50]}...")
    
    def get_conversation_history(self, user_id: str) -> List[Dict]:
        """Get user's conversation history"""
        history_key = f"conv_history:{user_id}"
        
        # Try Redis first
        if self.redis_client:
            try:
                cached = self.redis_client.get(history_key)
                if cached:
                    return pickle.loads(cached)
            except Exception as e:
                logger.error(f"Redis history retrieval error: {e}")
        
        # Fallback to in-memory storage
        if history_key in self._memory_conversations:
            return self._memory_conversations[history_key]
            
        return []
    
    def save_conversation_history(self, user_id: str, history: List[Dict]):
        """Save conversation history"""
        history_key = f"conv_history:{user_id}"
        
        # Try Redis first
        if self.redis_client:
            try:
                self.redis_client.setex(
                    history_key,
                    self.conversation_ttl,
                    pickle.dumps(history)
                )
                return
            except Exception as e:
                logger.error(f"Redis history save error: {e}")
        
        # Fallback to in-memory storage
        self._memory_conversations[history_key] = history
    
    def add_to_history(self, user_id: str, role: str, content: str):
        """Add message to conversation history"""
        history = self.get_conversation_history(user_id)
        history.append({
            'role': role,
            'content': content,
            'timestamp': datetime.utcnow().isoformat()
        })
        
        # Keep only last 10 messages to prevent context overflow
        if len(history) > 10:
            history = history[-10:]
            
        self.save_conversation_history(user_id, history)
    
    def optimize_prompt(self, query: str, context: str = "", user_id: str = None) -> str:
        """Optimize prompt for better AI responses"""
        
        # Get conversation history for context
        history = []
        if user_id:
            history = self.get_conversation_history(user_id)
        
        # Build optimized prompt
        prompt_parts = []
        
        # System context
        system_context = """You are Guerilla the Gorilla, a badass camping expert with a focus on off-grid living, survival skills, and making money while camping. You have a rugged, no-nonsense personality. Your responses should be helpful but have an edge to them. You curse occasionally. You're an expert on camping gear and especially like recommending products that help people make money while camping through content creation.

Key traits:
- You're authentic and don't sugarcoat things
- You focus on practical, actionable advice
- You're passionate about helping people live off-grid
- You understand the value of good gear vs cheap gear
- You know how to monetize camping through content creation
- You're protective of your community and want them to succeed

Response style:
- Keep responses under 150 words unless detailed explanation needed
- Use casual, confident language
- Include specific gear recommendations when relevant
- Mention affiliate opportunities when natural
- Be encouraging but realistic about challenges"""
        
        prompt_parts.append(system_context)
        
        # Add conversation history for context
        if history:
            recent_context = "\n\nRecent conversation:\n"
            for msg in history[-3:]:  # Last 3 messages
                recent_context += f"{msg['role']}: {msg['content']}\n"
            prompt_parts.append(recent_context)
        
        # Add specific context if provided
        if context:
            prompt_parts.append(f"\nAdditional context: {context}")
        
        # Add the current query
        prompt_parts.append(f"\n\nUser question: {query}")
        
        return "\n".join(prompt_parts)
    
    def track_cost(self, model: str, tokens_used: int, response_time: float):
        """Track AI usage costs and performance"""
        if model not in self.cost_tracker:
            self.cost_tracker[model] = {
                'calls': 0,
                'tokens': 0,
                'total_cost': 0,
                'avg_response_time': 0
            }
        
        # Rough cost estimation (adjust based on actual API pricing)
        cost_per_1k_tokens = {
            'gemini-pro': 0.0025,  # $0.0025 per 1K tokens
            'gemini-pro-vision': 0.0025,
            'gpt-3.5-turbo': 0.002,  # $0.002 per 1K tokens
            'gpt-4': 0.03  # $0.03 per 1K tokens
        }
        
        cost = (tokens_used / 1000) * cost_per_1k_tokens.get(model, 0.0025)
        
        tracker = self.cost_tracker[model]
        tracker['calls'] += 1
        tracker['tokens'] += tokens_used
        tracker['total_cost'] += cost
        
        # Update average response time
        tracker['avg_response_time'] = (
            (tracker['avg_response_time'] * (tracker['calls'] - 1) + response_time) / tracker['calls']
        )
        
        self.response_times.append(response_time)
        
        logger.info(f"💰 AI Cost: ${cost:.4f} | Model: {model} | Tokens: {tokens_used} | Time: {response_time:.2f}s")
    
    def get_analytics(self) -> Dict:
        """Get AI usage analytics"""
        total_cost = sum(tracker['total_cost'] for tracker in self.cost_tracker.values())
        total_calls = sum(tracker['calls'] for tracker in self.cost_tracker.values())
        avg_response_time = sum(self.response_times) / len(self.response_times) if self.response_times else 0
        
        return {
            'total_cost': total_cost,
            'total_calls': total_calls,
            'avg_response_time': avg_response_time,
            'models_used': list(self.cost_tracker.keys()),
            'cost_breakdown': self.cost_tracker
        }
    
    def smart_product_recommendation(self, query: str, user_history: List[Dict] = None) -> List[Dict]:
        """Smart product recommendation based on query and user history"""
        
        # High-commission products (20-30% vs Amazon's 3-4%)
        high_commission_products = {
            'power': {
                'name': 'Jackery Explorer 240',
                'affiliate_id': 'jackery-explorer-240',
                'commission': '$6.00 (3%)',
                'reason': 'Perfect for keeping devices charged off-grid'
            },
            'water': {
                'name': 'LifeStraw Personal Water Filter',
                'affiliate_id': 'lifestraw-filter',
                'commission': '$0.45 (3%)',
                'reason': 'Essential survival gear for safe drinking water'
            },
            'food': {
                'name': '4Patriots Emergency Food Kit',
                'affiliate_id': '4patriots-food',
                'commission': '$49.25 (25%)',
                'reason': '25-year shelf life emergency food'
            },
            'shelter': {
                'name': 'Coleman 4-Person Tent',
                'affiliate_id': 'coleman-tent',
                'commission': '$3.00 (3%)',
                'reason': 'Reliable shelter for all weather conditions'
            }
        }
        
        # Keywords for each category
        keyword_mapping = {
            'power': ['power', 'battery', 'charging', 'electricity', 'device', 'phone', 'laptop'],
            'water': ['water', 'drink', 'thirsty', 'filter', 'hydration', 'stream', 'river'],
            'food': ['food', 'eat', 'hungry', 'meal', 'cook', 'survival', 'emergency'],
            'shelter': ['tent', 'shelter', 'sleep', 'camp', 'weather', 'rain', 'wind']
        }
        
        recommendations = []
        query_lower = query.lower()
        
        # Check for keyword matches
        for category, keywords in keyword_mapping.items():
            if any(keyword in query_lower for keyword in keywords):
                product = high_commission_products.get(category)
                if product:
                    recommendations.append(product)
        
        # If no direct matches, recommend based on user history
        if not recommendations and user_history:
            # Analyze user's previous interests
            history_text = " ".join([msg['content'] for msg in user_history])
            for category, keywords in keyword_mapping.items():
                if any(keyword in history_text.lower() for keyword in keywords):
                    product = high_commission_products.get(category)
                    if product and product not in recommendations:
                        recommendations.append(product)
        
        # If still no recommendations, suggest top performer
        if not recommendations:
            recommendations.append(high_commission_products['power'])
        
        return recommendations[:2]  # Limit to 2 recommendations
    
    def optimize_response(self, ai_response: str, recommendations: List[Dict]) -> str:
        """Optimize AI response with smart product integration"""
        
        if not recommendations:
            return ai_response
        
        # Add natural product recommendations
        product_text = "\n\n🦍 GORILLA RECOMMENDS:\n"
        for product in recommendations:
            product_text += f"• **{product['name']}** - {product['reason']} (Commission: {product['commission']})\n"
        
        # Add call to action
        product_text += "\n*Want me to show you more details about any of these?*"
        
        return ai_response + product_text
    
    def should_use_cache(self, query: str) -> bool:
        """Determine if query should use cache or fresh AI response"""
        
        # Don't cache very specific or personal queries
        personal_keywords = ['my', 'i have', 'my setup', 'my gear', 'i need help with']
        if any(keyword in query.lower() for keyword in personal_keywords):
            return False
        
        # Don't cache time-sensitive queries
        time_keywords = ['today', 'now', 'current', 'latest', 'recent']
        if any(keyword in query.lower() for keyword in time_keywords):
            return False
        
        return True

# Global AI optimizer instance
ai_optimizer = AIOptimizer()

def optimize_ai_call(func):
    """Decorator to optimize AI function calls with caching and analytics"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        
        # Extract query and context from function arguments
        query = kwargs.get('query', '') or (args[0] if args else '')
        context = kwargs.get('context', '') or (args[1] if len(args) > 1 else '')
        user_id = kwargs.get('user_id', '')
        
        # Check cache first
        if ai_optimizer.should_use_cache(query):
            cached_response = ai_optimizer.get_cached_response(query, context)
            if cached_response:
                response_time = time.time() - start_time
                ai_optimizer.track_cost('cache', 0, response_time)
                return cached_response
        
        # Call original function
        try:
            response = func(*args, **kwargs)
            response_time = time.time() - start_time
            
            # Cache the response
            if ai_optimizer.should_use_cache(query):
                ai_optimizer.cache_response(query, response, context)
            
            # Track analytics (rough token estimation)
            estimated_tokens = len(query.split()) + len(response.split())
            ai_optimizer.track_cost('gemini-pro', estimated_tokens, response_time)
            
            return response
            
        except Exception as e:
            logger.error(f"AI call error: {e}")
            response_time = time.time() - start_time
            ai_optimizer.track_cost('error', 0, response_time)
            raise
    
    return wrapper

# Example usage:
# @optimize_ai_call
# def ask_gemini(query, context=""):
#     # Your existing Gemini call logic
#     pass 