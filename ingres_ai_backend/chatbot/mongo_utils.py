from pymongo import MongoClient
import os

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
client = MongoClient(MONGO_URI)
db = client["ingres_ai"]

def save_chat(role, message):
    db.chats.insert_one({"role": role, "message": message})
