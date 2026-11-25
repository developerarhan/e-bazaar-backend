"""
Agent Orchestrator — Phase 3 (Final)

The complete agent loop:
  1. Load short + long term memory
  2. RAG retrieval
  3. Build system prompt with context
  4. Call Groq with tool definitions
  5. IF tool call requested → execute → feed result back → goto 4
  6. UNTIL text response OR max rounds reached
  7. Save conversation history
  8. Extract long-term memories
"""

import json
import logging
from groq import Groq
from django.conf import settings

from .prompts import build_system_prompt, build_memory_extraction_prompt
from .memory import ShortTermMemory, LongTermMemory
from .rag import retrieve, format_context_for_prompt
from .tool_definitions import TOOLS
from .tools import execute_tool

logger = logging.getLogger('chat')

MAX_AGENT_ROUNDS = 3


class ChatOrchestrator:

    def __init__(self):
        if not settings.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY is not configured.")
        self.client = Groq(api_key=settings.GROQ_API_KEY)
        self.model = getattr(
            settings, 'GROQ_MODEL'
        )

    def respond(self, user_message, session_id, user=None, session_key=None):
        logger.info("Chat message received", extra={
            'session_id': session_id,
            'user_id': user.id if user and user.is_authenticated else None,
            'message_preview': user_message[:50],
        })

        # Step 1: Load memory
        history   = ShortTermMemory.get_history(session_id)
        long_term = LongTermMemory.get_memories(user=user, session_key=session_key)

        # Step 2: RAG retrieval
        retrieved_docs = retrieve(user_message)
        rag_context    = format_context_for_prompt(retrieved_docs)

        # Step 3: Build system prompt
        is_authenticated = bool(user and user.is_authenticated)
        system_prompt = build_system_prompt(
            user_memories=long_term if long_term.exists() else None,
            is_authenticated=is_authenticated,
            rag_context=rag_context if rag_context else None,
        )

        # Step 4: Build messages
        messages = [
            {"role": "system", "content": system_prompt},
            *history,
            {"role": "user", "content": user_message},
        ]

        # Step 5: Agent loop
        final_response = None
        tools_called   = []
        rounds         = 0

        while rounds < MAX_AGENT_ROUNDS:
            rounds += 1
            logger.debug("Agent round", extra={'round': rounds, 'session_id': session_id})

            response = self._call_groq_with_tools(
                messages,
                tools=TOOLS if rounds < MAX_AGENT_ROUNDS else None,
            )

            if self._wants_tool_call(response):
                tool_calls = response.choices[0].message.tool_calls

                messages.append({
                    "role": "assistant",
                    "content": response.choices[0].message.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in tool_calls
                    ],
                })

                for tc in tool_calls:
                    tool_name = tc.function.name
                    try:
                        tool_args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        tool_args = {}

                    tool_result = execute_tool(
                        tool_name=tool_name,
                        tool_args=tool_args,
                        user=user,
                    )

                    tools_called.append({'name': tool_name, 'args': tool_args})

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(tool_result, ensure_ascii=False),
                    })

                continue

            final_response = response.choices[0].message.content.strip()
            break

        if not final_response:
            final_response = (
                "I ran into an issue processing that. "
                "Please try again or contact support."
            )

        # Step 6: Save history
        ShortTermMemory.add_messages(session_id, user_message, final_response)

        # Step 7: Extract memories every 4 turns
        updated_history = ShortTermMemory.get_history(session_id)
        if len(updated_history) % 8 == 0:
            self._extract_and_save_memories(
                updated_history, user=user, session_key=session_key
            )

        logger.info("Agent response complete", extra={
            'session_id': session_id,
            'rounds': rounds,
            'tools_called': [t['name'] for t in tools_called],
            'rag_docs': len(retrieved_docs),
            'response_preview': final_response[:60],
        })

        return {
            'message':    final_response,
            'session_id': session_id,
            'tools_used': [t['name'] for t in tools_called],
            'rag_sources': len(retrieved_docs),
        }

    def _call_groq_with_tools(self, messages, tools=None):
        try:
            kwargs = {
                "model":       self.model,
                "messages":    messages,
                "temperature": 0.7,
                "max_tokens":  512,
            }
            if tools:
                kwargs["tools"]       = tools
                kwargs["tool_choice"] = "auto"

            return self.client.chat.completions.create(**kwargs)

        except Exception as e:
            logger.error("Groq API call failed", extra={'error': str(e)}, exc_info=True)
            return _FallbackResponse(
                "I'm having trouble connecting right now. Please try again."
            )

    @staticmethod
    def _wants_tool_call(response) -> bool:
        try:
            choice = response.choices[0]
            return (
                hasattr(choice.message, 'tool_calls')
                and choice.message.tool_calls
                and len(choice.message.tool_calls) > 0
            )
        except (AttributeError, IndexError):
            return False

    def _extract_and_save_memories(self, history, user=None, session_key=None):
        if len(history) < 4:
            return
        try:
            extraction_prompt = build_memory_extraction_prompt(history)
            response = self.client.chat.completions.create(
                model=getattr(
                    settings, 'GROQ_MODEL'
                ),
                messages=[{"role": "user", "content": extraction_prompt}],
                temperature=0.1,
                max_tokens=300,
            )
            raw = response.choices[0].message.content.strip()
            if raw.startswith('```'):
                raw = raw.split('```')[1]
                if raw.startswith('json'):
                    raw = raw[4:]
            extracted = json.loads(raw.strip())
            if isinstance(extracted, list) and extracted:
                LongTermMemory.save_memories(extracted, user=user, session_key=session_key)
                logger.info("Memories extracted", extra={'count': len(extracted)})
        except json.JSONDecodeError:
            logger.debug("Memory extraction non-JSON — skipped")
        except Exception as e:
            logger.warning("Memory extraction failed", extra={'error': str(e)})


class _FallbackResponse:
    def __init__(self, message: str):
        self.choices = [_FallbackChoice(message)]

class _FallbackChoice:
    def __init__(self, message: str):
        self.message = _FallbackMessage(message)

class _FallbackMessage:
    def __init__(self, content: str):
        self.content    = content
        self.tool_calls = None
