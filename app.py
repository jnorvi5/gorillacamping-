import os
import uuid
import json
import random
import time
from datetime import datetime
from flask import Flask, render_template, jsonify, request, redirect, url_for, session, make_response
from flask_cors import CORS
import requests
from opencensus.ext.azure.log_exporter import AzureLogHandler
import logging

# --- FLASK SETUP ---
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'gorilla-secret-2025')

# Configure CORS for your domains
CORS(app, origins=[
    "https://gorillacamping.site", 
    "https://www.gorillacamping.site",
    "http://localhost:3000",  # For local development
], supports_credentials=True)

# Set up logging with Azure Application Insights
logger = logging.getLogger(__name__)
# Fix the Azure Application Insights connection
connection_string = os.environ.get('APPLICATIONINSIGHTS_CONNECTION_STRING')
if connection_string:
    logger.addHandler(AzureLogHandler(connection_string=connection_string))
    logger.info("Azure Application Insights configured successfully")
else:
    logger.warning("No Azure Application Insights connection string found")

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

# --- AZURE SPECIFIC VARIABLES ---
AZURE_OPENAI_ENDPOINT = os.environ.get('AZURE_OPENAI_ENDPOINT')
AZURE_OPENAI_KEY = os.environ.get('AZURE_OPENAI_KEY')
AZURE_OPENAI_DEPLOYMENT_NAME = os.environ.get('AZURE_OPENAI_DEPLOYMENT_NAME')

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

