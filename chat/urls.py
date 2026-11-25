from django.urls import path
from .views import ChatMessageView, ChatHistoryView, ChatClearView
 
urlpatterns = [
    path('message/', ChatMessageView.as_view()),
    path('history/', ChatHistoryView.as_view()),
    path('clear/',   ChatClearView.as_view()),
]
 
