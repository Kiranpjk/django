# chatbot/views.py
import os
from datetime import datetime
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from pymongo import MongoClient
from bson import ObjectId

import google.genai as genai
from google.api_core.exceptions import ResourceExhausted

# -----------------------------------
# Configuration
# -----------------------------------
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
MONGO_DB = os.getenv("MONGO_DB", "ingres_ai_db")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

mongo_client = MongoClient(MONGO_URI)
db = mongo_client[MONGO_DB]
chats_collection = db["chats"]

ai_client = genai.Client(api_key=GEMINI_API_KEY)

# -----------------------------------
# Helpers
# -----------------------------------
def _user_identifier(request):
    if not request.session.session_key:
        request.session.create()
    return f"anon:{request.session.session_key}"

def _to_jsonable(doc):
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id"))
    msgs = doc.get("messages", [])
    for m in msgs:
        if isinstance(m.get("ts"), datetime):
            m["ts"] = m["ts"].isoformat()
    return doc

# -----------------------------------
# POST /api/chat/
# Sends a message or creates chat (new_chat)
# -----------------------------------
@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def chat_view(request):
    data = request.data or {}
    query = (data.get("query") or "").strip()
    is_new_chat = data.get("new_chat", False)
    chat_id = data.get("chat_id")
    user_id = _user_identifier(request)

    try:
        # New chat
        if is_new_chat:
            new_chat = {
                "user_identifier": user_id,
                "title": "New Chat",
                "messages": [],
                "created_at": datetime.utcnow(),
            }
            res = chats_collection.insert_one(new_chat)
            chat_id = str(res.inserted_id)
            request.session["chat_id"] = chat_id
            return JsonResponse({"message": "New chat created", "chat_id": chat_id})

        if not query:
            return JsonResponse({"error": "Empty query ignored"}, status=400)

        # Find or create chat
        if chat_id:
            chat_doc = chats_collection.find_one({"_id": ObjectId(chat_id), "user_identifier": user_id})
            if not chat_doc:
                return JsonResponse({"error": "Chat not found"}, status=404)
        else:
            chat_id = request.session.get("chat_id")
            if not chat_id:
                new_chat = {
                    "user_identifier": user_id,
                    "title": query[:60],
                    "messages": [],
                    "created_at": datetime.utcnow(),
                }
                res = chats_collection.insert_one(new_chat)
                chat_id = str(res.inserted_id)
                request.session["chat_id"] = chat_id

        # Save user message
        user_msg = {"role": "user", "content": query, "ts": datetime.utcnow()}
        chats_collection.update_one({"_id": ObjectId(chat_id)}, {"$push": {"messages": user_msg}})

        # Update title if default
        chat_doc = chats_collection.find_one({"_id": ObjectId(chat_id)})
        if chat_doc.get("title") == "New Chat":
            chats_collection.update_one({"_id": ObjectId(chat_id)}, {"$set": {"title": query[:60]}})

        # AI generation
        system = (
            "You are INGRES AI Assistant for the Central Ground Water Board of India. "
            "Help users understand groundwater, extraction rates, recharge, and classifications."
        )
        full_prompt = f"{system}\n\nUser: {query}"

        try:
            response = ai_client.models.generate_content(model="models/gemini-2.5-flash", contents=full_prompt)
            answer = getattr(response, "text", "").strip() or "No answer generated."
        except ResourceExhausted:
            answer = "⚠️ Gemini quota exceeded."
        except Exception:
            answer = "⚠️ AI backend error."

        assistant_msg = {"role": "assistant", "content": answer, "ts": datetime.utcnow()}
        chats_collection.update_one({"_id": ObjectId(chat_id)}, {"$push": {"messages": assistant_msg}})

        return JsonResponse({"answer": answer, "chat_id": chat_id})

    except Exception as e:
        print("🔥 ERROR in chat_view:", repr(e))
        return JsonResponse({"error": str(e)}, status=500)

# -----------------------------------
# GET /api/chats/
# -----------------------------------
@api_view(["GET"])
@permission_classes([AllowAny])
def get_chats(request):
    try:
        user_id = _user_identifier(request)
        docs = list(chats_collection.find({"user_identifier": user_id}).sort("created_at", -1))
        return JsonResponse([_to_jsonable(d) for d in docs], safe=False)
    except Exception as e:
        print("🔥 ERROR in get_chats:", repr(e))
        return JsonResponse({"error": str(e)}, status=500)

# -----------------------------------
# POST /api/chat/delete/  { chat_id }
# -----------------------------------
@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def delete_chat(request):
    data = request.data or {}
    chat_id = data.get("chat_id")
    user_id = _user_identifier(request)
    if not chat_id:
        return JsonResponse({"error": "chat_id required"}, status=400)
    try:
        res = chats_collection.delete_one({"_id": ObjectId(chat_id), "user_identifier": user_id})
        if res.deleted_count == 0:
            return JsonResponse({"error": "Chat not found"}, status=404)
        # clear session if deleted current
        if request.session.get("chat_id") == chat_id:
            request.session.pop("chat_id", None)
        return JsonResponse({"message": "deleted", "chat_id": chat_id})
    except Exception as e:
        print("🔥 ERROR delete_chat:", repr(e))
        return JsonResponse({"error": str(e)}, status=500)

# -----------------------------------
# POST /api/chat/rename/  { chat_id, title }
# -----------------------------------
@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def rename_chat(request):
    data = request.data or {}
    chat_id = data.get("chat_id")
    title = (data.get("title") or "").strip()
    user_id = _user_identifier(request)
    if not chat_id or not title:
        return JsonResponse({"error": "chat_id and title required"}, status=400)
    try:
        res = chats_collection.update_one({"_id": ObjectId(chat_id), "user_identifier": user_id}, {"$set": {"title": title}})
        if res.matched_count == 0:
            return JsonResponse({"error": "Chat not found"}, status=404)
        return JsonResponse({"message": "renamed", "chat_id": chat_id, "title": title})
    except Exception as e:
        print("🔥 ERROR rename_chat:", repr(e))
        return JsonResponse({"error": str(e)}, status=500)

# -----------------------------------
# POST /api/chats/clear/  (clear all for this session)
# -----------------------------------
@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def clear_chats(request):
    user_id = _user_identifier(request)
    try:
        res = chats_collection.delete_many({"user_identifier": user_id})
        request.session.pop("chat_id", None)
        return JsonResponse({"message": "cleared", "deleted_count": res.deleted_count})
    except Exception as e:
        print("🔥 ERROR clear_chats:", repr(e))
        return JsonResponse({"error": str(e)}, status=500)
@api_view(["POST"])
def create_chat(request):
    user = request.user

    chat = Chat.objects.create(
        user=user,
        title="New Chat",
        messages=[]
    )

    return Response({"chat_id": chat.id})
@api_view(["GET"])
def get_user_chats(request):
    user = request.user
    chats = Chat.objects.filter(user=user).order_by("-created_at")

    return Response([
        {
            "id": c.id,
            "title": c.title,
            "messages": c.messages
        }
        for c in chats
    ])
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ]
}
