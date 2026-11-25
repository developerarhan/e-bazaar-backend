import uuid
import logging
 
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
 
from .agent.orchestrator import ChatOrchestrator
from .agent.memory import ShortTermMemory, LongTermMemory
 
logger = logging.getLogger('chat')
 
 
class ChatMessageView(APIView):
    """
    POST /api/chat/message/
 
    Main chat endpoint. Accepts a message and returns
    the assistant's response.
 
    Body:
      {
        "message": "do you have wireless earbuds?",
        "session_id": "abc123"   ← optional, generated if missing
      }
 
    Returns:
      {
        "message": "Yes! Here are our wireless earbuds...",
        "session_id": "abc123"   ← always returned for frontend to store
      }
 
    Auth: Optional — authenticated users get order lookup capability
          and memories tied to their account (not just session).
    """
    permission_classes = [AllowAny]
 
    def post(self, request):
        message = request.data.get('message', '').strip()
        session_id = request.data.get('session_id', '').strip()
 
        # ── Validate ───────────────────────────────────────────────
        if not message:
            return Response(
                {'error': 'Message is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
 
        if len(message) > 1000:
            return Response(
                {'error': 'Message is too long (max 1000 characters).'},
                status=status.HTTP_400_BAD_REQUEST
            )
 
        # ── Session ID ─────────────────────────────────────────────
        # Frontend stores this in localStorage and sends it
        # with every message — gives conversation continuity.
        # If missing (first message), generate a new one.
        if not session_id:
            session_id = str(uuid.uuid4())
 
        # ── Identify user ──────────────────────────────────────────
        user = request.user if request.user.is_authenticated else None
 
        # For anonymous users, use session_id as their identifier
        # so memories can still be stored/retrieved
        session_key = session_id if not user else ''
 
        # ── Call agent ─────────────────────────────────────────────
        try:
            orchestrator = ChatOrchestrator()
            result = orchestrator.respond(
                user_message=message,
                session_id=session_id,
                user=user,
                session_key=session_key,
            )
        except ValueError as e:
            # GROQ_API_KEY not configured
            logger.error("Chat not configured", extra={'error': str(e)})
            return Response(
                {'error': 'Chat is not available right now.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        except Exception as e:
            logger.error("Unexpected chat error", extra={
                'error': str(e),
                'session_id': session_id,
            }, exc_info=True)
            return Response(
                {'error': 'Something went wrong. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
 
        return Response({
            'message': result['message'],
            'session_id': result['session_id'],
        })
 
 
class ChatHistoryView(APIView):
    """
    GET /api/chat/history/?session_id=abc123
 
    Returns conversation history for the given session.
    Used when user opens the chat widget — restores
    the conversation they were having.
    """
    permission_classes = [AllowAny]
 
    def get(self, request):
        session_id = request.query_params.get('session_id', '').strip()
 
        if not session_id:
            return Response({'messages': []})
 
        history = ShortTermMemory.get_history(session_id)
 
        return Response({
            'messages': history,
            'session_id': session_id,
        })
 
 
class ChatClearView(APIView):
    """
    POST /api/chat/clear/
 
    Clears conversation history for the session.
    Long-term memories are preserved (intentional —
    clearing a chat doesn't make the bot forget you).
 
    Body: { "session_id": "abc123" }
    """
    permission_classes = [AllowAny]
 
    def post(self, request):
        session_id = request.data.get('session_id', '').strip()
 
        if not session_id:
            return Response(
                {'error': 'session_id is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
 
        ShortTermMemory.clear(session_id)
 
        return Response({'message': 'Conversation cleared.'})
 