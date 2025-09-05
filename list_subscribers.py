
from pymongo import MongoClient
import os

# Use the same env var name as the app
client = MongoClient(os.environ["MONGODB_URI"])
# Allow overriding DB name; default to 'gorillacamping'
db_name = os.environ.get("MONGODB_DB_NAME", "gorillacamping")
db = client[db_name]
subscribers = db["subscribers"]

print("Email Subscribers:")
for sub in subscribers.find():
    print(sub)
