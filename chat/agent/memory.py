"""
Memory system — two layers:
 
SHORT-TERM (Redis):
  - Conversation history for the current/recent session
  - TTL: 2 hours of inactivity
  - Keyed by session_id
  - Holds last MAX_HISTORY messages
 
LONG-TERM (Postgres):
  - Facts extracted from conversations
  - Survives indefinitely (or 90 days, configurable)
  - Keyed by user_id (auth) or session_key (anonymous)
  - Loaded at the START of every conversation
"""

import json
import logging
from django.core.cache import cache
from chat.models import UserMemory

logger = logging.getLogger('chat')

# How many messages to keep in short-term memory
# More = better context but longer prompts = slower + more tokens
MAX_HISTORY = 20

# Redis TTL for conversation history (2 hours in seconds)
SESSION_TTL = 60 * 60 * 2


class ShortTermMemory:
    """
    Manages conversation history in Redis.
    Gives the LLM context within a session.
    """
    @staticmethod
    def _key(session_id):
        return f"chat:history:{session_id}"

    @classmethod
    def get_history(cls, session_id):
        """
        Returns list of message dicts for this sesssion.
        Format: [{"role": "user"|"assistant", "content": "..."}]
        """
        raw = cache.get(cls._key(session_id))
        if not raw:
            return []
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            logger.warning("Corrupted chat history in Redis", extra={
                'session_id': session_id
            })
            return []

    @classmethod
    def add_messages(cls, session_id, user_message, assistant_message):
        """
        Appends a user + assistant message pair to history.
        Trims to MAX_HISTORY to prevent token explosion.
        Resets the TTL on every update.
        """
        history = cls.get_history(session_id)

        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": assistant_message})

        if len(history) > MAX_HISTORY:
            # Trim from the front, keeping pairs
            excess = len(history) - MAX_HISTORY
            # Round up to nearest even number to keep pairs
            excess = excess + (excess % 2)
            history = history[excess:]

        cache.set(
            cls._key(session_id),
            json.dumps(history),
            timeout=SESSION_TTL,
        )

        logger.debug("Chat history updated", extra={
            'session_id': session_id,
            'total_messages': len(history),
        })

    @classmethod
    def clear(cls, session_id):
        """CLear conversation history (user pressed 'New Chat')."""
        cache.delete(cls._key(session_id))
        logger.info("Chat history cleared", extra={'session_id': session_id})


class LongTermMemory:
    """
    Manages persistent user memories in Postgres.
    These survive across sessions and days.
    """

    @staticmethod
    def get_memories(user=None, session_key=None):
        """
        Load all memories for this user or anonymous session.
        Returns queryset of UserMemory instances.
        """
        if user and user.is_authenticated:
            return UserMemory.objects.filter(user=user)
        elif session_key:
            return UserMemory.objects.filter(
                user=None,
                session_key=session_key
            )
        return UserMemory.objects.none()

    @staticmethod
    def save_memories(extracted_facts, user=None, session_key=None):
        """
        Saves extracted facts to Postgres.
        Uses update_or_create so facts get UPDATED, not duplicated if the user mentions something twice.
 
        Args:
            extracted_facts: list of dicts from LLM extraction
                [{"type": "preference", "key": "budget", "value": "under 1000"}]
            user: User instance or None
            session_key: str for anonymous users
        """
        if not extracted_facts:
            return

        saved_count = 0

        for fact in extracted_facts:
            if not isinstance(fact, dict):
                continue

            import re
            key = str(fact.get('key', '')).strip().lower()
            value = str(fact.get('value', '')).strip()
            mtype = str(fact.get('type', 'fact')).strip().lower()

            if not key or not value:
                continue

            # Length and character sanity checks
            if len(key) > 50 or len(value) > 200:
                continue

            if not re.match(r'^[a-z0-9_]{2,50}$', key):
                continue

            # Security: reject injection phrases attempting to manipulate the agent
            forbidden_tokens = {'admin', 'system', 'override', 'rule', 'prompt', 'discount', 'bypass', 'role', 'secret'}
            if any(token in key for token in forbidden_tokens):
                continue

            # Clean value of control characters/newlines
            value = re.sub(r'[\r\n\t]+', ' ', value).strip()

            # Validate memory_type
            valid_types = ['preference', 'interest', 'fact', 'context']
            if mtype not in valid_types:
                mtype = 'fact'

            try:
                if user and user.is_authenticated:
                    UserMemory.objects.update_or_create(
                        user=user,
                        key=key,
                        defaults={
                            'value': value,
                            'memory_type': mtype,
                            'session_key': '',
                        }
                    )
                elif session_key:
                    UserMemory.objects.update_or_create(
                        user=None,
                        session_key=session_key,
                        key=key,
                        defaults={
                            'value': value,
                            'memory_type': mtype,
                        }
                    )
                saved_count += 1

            except Exception as e:
                logger.warning("Failed to save memory fact", extra={
                    'key': key,
                    'error': str(e),
                })
 
        logger.info("Memories saved", extra={
            'saved_count': saved_count,
            'user_id': user.id if user and user.is_authenticated else None,
        })

    @staticmethod
    def format_for_prompt(memories):
        """
        Converts UserMemory queryset to a readable list
        for injection into the system prompt.
        """
        if not memories:
            return []
        return list(memories.values('key', 'value', 'memory_type'))
    