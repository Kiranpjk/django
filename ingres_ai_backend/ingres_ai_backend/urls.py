# ingres_ai_backend/urls.py
from django.contrib import admin
from django.urls import path
from django.urls import path, include

urlpatterns = [
    path("accounts/", include("allauth.urls")),
]

from chatbot.views import (
    chat_view,
    get_chats,
    delete_chat,
    rename_chat,
    clear_chats,
)

urlpatterns = [
    path("admin/", admin.site.urls),

    path("api/chat/", chat_view),
    path("api/chats/", get_chats),

    path("api/chat/delete/", delete_chat),
    path("api/chat/rename/", rename_chat),
    path("api/chats/clear/", clear_chats),
]
