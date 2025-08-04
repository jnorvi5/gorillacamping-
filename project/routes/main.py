from flask import Blueprint, render_template, redirect, request
from ..services.product_service import ProductService
from ..services.storage_service import StorageService

main_bp = Blueprint('main', __name__)
product_service = ProductService()
# Note: storage_service will be initialized in the app factory
storage_service = None

def init_app(app, ss):
    global storage_service
    storage_service = ss

@main_bp.route('/')
def home():
    return render_template('index.html')

@main_bp.route('/blog')
def blog():
    return render_template('blog.html')

@main_bp.route('/blog/<slug>')
def blog_post(slug):
    return render_template('post.html')

@main_bp.route('/gear')
def gear():
    return render_template('gear.html')

@main_bp.route('/about')
def about():
    return render_template('about.html')

@main_bp.route('/contact')
def contact():
    return render_template('contact.html')

@main_bp.route('/affiliate/<product>')
def affiliate(product):
    """Track and redirect affiliate clicks"""
    # Track the click with source
    source = request.args.get('source')
    storage_service.track_affiliate_click(product, source)

    link = product_service.get_affiliate_link(product)
    return redirect(link or '/gear')

@main_bp.route('/social/<platform>')
def social_redirect(platform):
    """Track and redirect social media clicks"""
    social_links = {
        'reddit': 'https://www.reddit.com/r/gorillacamping',
        'facebook': 'https://www.facebook.com/profile.php?id=61577334442896',
        'tiktok': 'https://www.tiktok.com/@gorillacamping'
    }
    return redirect(social_links.get(platform, '/'))
