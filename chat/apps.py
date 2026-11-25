from django.apps import AppConfig


class ChatConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'chat'
    verbose_name = 'AI Chat'

    def ready(self):
        # Register signals when app loads
        import chat.signals 
    