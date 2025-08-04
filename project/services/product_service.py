import random

class ProductService:
    def __init__(self):
        self.product_triggers = {
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
        self.gear_items = [
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
        self.affiliate_links = {
            'jackery-explorer-240': 'https://amzn.to/3QZqX8Y',
            'lifestraw-filter': 'https://amzn.to/3QZqX8Y',
            '4patriots-food': 'https://4patriots.com/products/4week-food?drolid=0001',
            'alps-lynx': 'https://amzn.to/3QZqX8Y'
        }

    def enhance_response_with_products(self, user_message, ai_response):
        """Add specific product recommendations based on context"""
        recommendations = []

        # Check both user message and AI response for relevant keywords
        combined_text = (user_message + " " + ai_response).lower()

        for category, product in self.product_triggers.items():
            for keyword in product['keywords']:
                if keyword in combined_text and product not in recommendations:
                    recommendations.append(product)
                    break

        # Limit to 1 recommendation per response to avoid overwhelming the user
        if len(recommendations) > 1:
            recommendations = [random.choice(recommendations)]

        return recommendations

    def get_gear(self):
        return self.gear_items

    def get_affiliate_link(self, product):
        return self.affiliate_links.get(product)
