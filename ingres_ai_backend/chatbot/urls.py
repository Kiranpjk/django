from django.contrib import admin
from django.urls import path
from chatbot.views import chat_view, get_chats, register_user, login_user, logout_user

urlpatterns = [
    path("admin/", admin.site.urls),

    path("api/chat/", chat_view),
    path("api/chats/", get_chats),

    path("api/register/", register_user),
    path("api/login/", login_user),
    path("api/logout/", logout_user),
]
