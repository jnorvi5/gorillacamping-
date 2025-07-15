#!/usr/bin/env python3
"""
🚀 Optimized App Startup Script

This script provides a clean way to start the app with optimized settings
and better error handling.
"""

import os
import sys
import time
from pathlib import Path

def check_dependencies():
    """Check and report on dependency availability"""
    dependencies = {
        'flask': 'Flask',
        'pymongo': 'MongoDB support',
        'redis': 'Redis caching',
        'google.generativeai': 'AI features',
        'flask_compress': 'Response compression'
    }
    
    available = {}
    
    print("🔍 Checking dependencies...")
    for module, description in dependencies.items():
        try:
            __import__(module)
            available[module] = True
            print(f"   ✅ {description}")
        except ImportError:
            available[module] = False
            print(f"   ⚠️  {description} (optional)")
    
    return available

def optimize_environment():
    """Set optimized environment variables"""
    optimizations = {
        'FLASK_ENV': 'production',
        'PYTHONUNBUFFERED': '1',
        'PYTHONDONTWRITEBYTECODE': '1',
        'WERKZEUG_RUN_MAIN': 'true'
    }
    
    for key, value in optimizations.items():
        if key not in os.environ:
            os.environ[key] = value
    
    print("⚙️  Environment optimized for production")

def main():
    """Main startup function"""
    print("🦍 Gorilla Camping - Optimized Startup")
    print("=" * 40)
    
    # Check dependencies
    available = check_dependencies()
    
    # Optimize environment
    optimize_environment()
    
    # Import and start the app
    print("\n🚀 Starting optimized application...")
    
    try:
        # Import the main app
        if os.path.exists('app_optimized.py'):
            print("   Using app_optimized.py")
            from app_optimized import app
        else:
            print("   Using app.py")
            from app import app
        
        # Configure for optimal performance
        app.config.update(
            SEND_FILE_MAX_AGE_DEFAULT=86400,  # 1 day cache for static files
            PERMANENT_SESSION_LIFETIME=1800,  # 30 minutes
            SESSION_COOKIE_HTTPONLY=True,
            SESSION_COOKIE_SAMESITE='Lax',
        )
        
        # Get port from environment
        port = int(os.environ.get('PORT', 5000))
        host = os.environ.get('HOST', '0.0.0.0')
        
        print(f"   Starting on {host}:{port}")
        print("   Ready for requests!")
        print("\n✅ Startup complete - all systems go!")
        
        # Start the application
        app.run(host=host, port=port, debug=False, threaded=True)
        
    except Exception as e:
        print(f"❌ Startup failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()