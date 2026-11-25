from django.contrib import admin

from .models import ChatConversation, EmbeddingDocument, UserMemory

admin.site.register([ChatConversation, EmbeddingDocument, UserMemory])
