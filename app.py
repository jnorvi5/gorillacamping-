import os
from flask import Flask, render_template, request, redirect, url_for
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from datetime import datetime
import requests

app = Flask(__name__)

# ---- MailerLite Integration ----
def add_to_mailerlite(email):
    api_key = os.environ.get("MAILERLITE_API_KEY")
    if not api_key:
        print("MailerLite API key missing!")
        return False
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    data = {
        "email": email
    }
    url = "https://connect.mailerlite.com/api/subscribers"
    response = requests.post(url, headers=headers, json=data)
    if response.status_code in (200, 201):
        print("Added to MailerLite!")
        return True
    else:
        print("MailerLite error:", response.text)
        return False

# Load MongoDB connection string from environment variable
MONGO_URI = os.environ.get("MONGO_URI")
if not MONGO_URI:
    raise ValueError("❌ MONGO_URI environment variable is not set!")

# Connect to MongoDB with URI
client = MongoClient(MONGO_URI, server_api=ServerApi('1'))

# Confirm MongoDB connection
try:
    client.admin.command("ping")
    print("✅ MongoDB connected successfully")
except Exception as e:
    print("❌ MongoDB connection failed:", e)
    raise

@app.route("/pingdb")
def pingdb():
    try:
        client.admin.command("ping")
        return "MongoDB connected!", 200
    except Exception as e:
        return f"MongoDB connection failed: {e}", 500

# Database setup
db = client.get_database("gorillacamping")
emails = db.get_collection("subscribers")
posts = db.get_collection("posts")

# Home route: handle newsletter form
@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        email = request.form.get("email")
        if email:
            emails.insert_one({
                "email": email,
                "timestamp": datetime.utcnow()
            })
            add_to_mailerlite(email)  # Add to MailerLite!
            return redirect(url_for("home"))
    return render_template("index.html")

# Blog listing
@app.route("/blog")
def blog():
    all_posts = posts.find().sort("created_at", -1)
    return render_template("blog.html", posts=all_posts)

# Individual blog post
@app.route("/blog/<slug>")
def blog_post(slug):
    post = posts.find_one({"slug": slug})
    if not post:
        return "404 Not Found", 404
    return render_template("post.html", post=post)

if __name__ == "__main__":
    app.run(debug=True)
