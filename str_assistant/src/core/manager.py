"""Agent Manager for the STR Assistant."""

import inspect
from collections.abc import AsyncGenerator
from typing import Any, Dict
from uuid import uuid4

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.pregel import Pregel
from langgraph.types import Command, Interrupt, Overwrite

from str_assistant.src.core.agent import get_str_agent
from str_assistant.src.core.agent_utils import (
    convert_message_content_to_string,
    langchain_to_chat_message,
    remove_tool_calls,
)
from str_assistant.src.core.storage import register_thread
from str_assistant.src.schema import StreamRequest
from str_assistant.src.settings import settings
from str_assistant.utils.pylogger import get_python_logger

app_logger = get_python_logger(settings.PYTHON_LOG_LEVEL)


class AgentManager:
    """Manages STR agent operations and streaming responses."""

    def __init__(self, sso_token: str | None = None):
        self.sso_token = sso_token
        self._agent: Pregel | None = None
        self._current_tool_call_id: str | None = None
        self._seen_message_ids: set = set()

    async def stream_response(
        self, request: StreamRequest
    ) -> AsyncGenerator[Dict[str, Any], None]:
        async with get_str_agent(self.sso_token) as persistent_agent:
            try:
                self._current_tool_call_id = None
                self._seen_message_ids = set()

                kwargs, run_id, thread_id = await self._handle_input(request, persistent_agent)

                app_logger.info(f"Streaming response for run_id={run_id}, thread_id={thread_id}")

                async for stream_event in persistent_agent.astream(
                    **kwargs, stream_mode=["updates", "messages", "custom"]
                ):
                    if not isinstance(stream_event, tuple):
                        continue

                    stream_mode, event = stream_event
                    self._update_tool_call_tracking(stream_mode, event)

                    effective_session_id = request.session_id or thread_id
                    formatted_events = self._format_events(
                        stream_mode, event, request.stream_tokens, run_id, thread_id, effective_session_id
                    )

                    for formatted_event in formatted_events:
                        if formatted_event:
                            yield formatted_event

            except Exception as e:
                app_logger.error(f"Error in stream_response: {e}", exc_info=True)
                yield {
                    "type": "error",
                    "content": {
                        "message": "Internal server error",
                        "recoverable": False,
                        "error_type": "agent_error",
                    },
                }

    async def _handle_input(
        self, request: StreamRequest, agent: Pregel
    ) -> tuple[Dict[str, Any], str, str]:
        run_id = uuid4()
        thread_id = request.thread_id or str(uuid4())
        effective_session_id = request.session_id or thread_id
        effective_user_id = request.user_id or "anonymous"

        if settings.USE_INMEMORY_SAVER:
            register_thread(effective_user_id, thread_id)

        ai_call_id = f"ai_call_{str(uuid4())}"
        configurable = {
            "thread_id": thread_id,
            "session_id": effective_session_id,
            "run_id": str(run_id),
            "user_id": effective_user_id,
            "ai_call_id": ai_call_id,
        }

        # Try to set up Langfuse callback if configured
        callbacks = []
        if settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY:
            try:
                from langfuse.langchain import CallbackHandler
                callbacks.append(CallbackHandler())
            except ImportError:
                pass

        config = RunnableConfig(
            configurable=configurable,
            run_id=run_id,
            callbacks=callbacks,
        )

        state = await agent.aget_state(config=config)
        existing_messages = state.values.get("messages", [])
        for msg in existing_messages:
            msg_id = getattr(msg, "id", None)
            if msg_id:
                self._seen_message_ids.add(msg_id)

        interrupted_tasks = [
            task for task in state.tasks
            if hasattr(task, "interrupts") and task.interrupts
        ]

        if interrupted_tasks:
            user_input_message = Command(resume=request.message)
        else:
            user_input_message = {"messages": [HumanMessage(content=request.message)]}

        return {"input": user_input_message, "config": config}, str(run_id), thread_id

    def _format_events(
        self, stream_mode: str, event: Any, stream_tokens: bool,
        run_id: str, thread_id: str, session_id: str | None,
    ) -> list[Dict[str, Any]]:
        formatted_events = []

        if stream_mode == "updates":
            formatted_events.extend(
                self._handle_update_events(event, run_id, thread_id, session_id)
            )
        elif stream_mode == "messages" and stream_tokens:
            token_event = self._handle_token_events(event)
            if token_event:
                formatted_events.append(token_event)
        elif stream_mode == "custom":
            custom_event = self._handle_custom_events(event, run_id, thread_id, session_id)
            if custom_event:
                formatted_events.append(custom_event)

        return formatted_events

    def _handle_update_events(
        self, event: Dict[str, Any], run_id: str, thread_id: str, session_id: str | None
    ) -> list[Dict[str, Any]]:
        formatted_events = []
        new_messages = []

        for node, updates in event.items():
            if node == "__interrupt__":
                interrupt: Interrupt
                for interrupt in updates:
                    new_messages.append(AIMessage(content=interrupt.value))
                continue

            updates = updates or {}
            raw_messages = updates.get("messages", [])
            is_overwrite = isinstance(raw_messages, Overwrite)
            update_messages = raw_messages.value if is_overwrite else raw_messages

            if is_overwrite:
                unseen = []
                for msg in update_messages:
                    msg_id = getattr(msg, "id", None) or id(msg)
                    if msg_id not in self._seen_message_ids:
                        unseen.append(msg)
                        self._seen_message_ids.add(msg_id)
                update_messages = unseen
            else:
                for msg in update_messages:
                    msg_id = getattr(msg, "id", None) or id(msg)
                    self._seen_message_ids.add(msg_id)

            if node == "supervisor":
                ai_messages = [msg for msg in update_messages if isinstance(msg, AIMessage)]
                if ai_messages:
                    update_messages = [ai_messages[-1]]

            new_messages.extend(update_messages)

        processed_messages = self._process_message_tuples(new_messages)

        for message in processed_messages:
            try:
                if isinstance(message, AIMessage) and not message.content and not getattr(message, "tool_calls", None):
                    continue

                chat_message = langchain_to_chat_message(message)
                chat_message.run_id = run_id

                formatted_event = {
                    "type": "message",
                    "content": self._convert_chat_message_to_simple_format(
                        chat_message, thread_id, session_id
                    ),
                }
                formatted_events.append(formatted_event)
            except Exception as e:
                app_logger.error(f"Error formatting message: {e}")

        return formatted_events

    def _handle_token_events(self, event: tuple) -> Dict[str, Any] | None:
        msg, metadata = event
        if "skip_stream" in metadata.get("tags", []):
            return None
        if not isinstance(msg, AIMessageChunk):
            return None

        content = remove_tool_calls(msg.content)
        if content:
            return {
                "type": "token",
                "content": convert_message_content_to_string(content),
            }
        return None

    def _handle_custom_events(
        self, event: Any, run_id: str, thread_id: str, session_id: str | None
    ) -> Dict[str, Any] | None:
        try:
            chat_message = langchain_to_chat_message(event)
            chat_message.run_id = run_id
            return {
                "type": "message",
                "content": self._convert_chat_message_to_simple_format(
                    chat_message, thread_id, session_id
                ),
            }
        except Exception as e:
            app_logger.error(f"Error handling custom event: {e}")
            return None

    def _process_message_tuples(self, new_messages: list) -> list:
        processed_messages = []
        current_message: Dict[str, Any] = {}

        for message in new_messages:
            if isinstance(message, tuple):
                key, value = message
                current_message[key] = value
            else:
                if current_message:
                    processed_messages.append(self._create_ai_message(current_message))
                    current_message = {}
                processed_messages.append(message)

        if current_message:
            processed_messages.append(self._create_ai_message(current_message))

        return processed_messages

    def _create_ai_message(self, parts: Dict[str, Any]) -> AIMessage:
        sig = inspect.signature(AIMessage)
        valid_keys = set(sig.parameters)
        filtered = {k: v for k, v in parts.items() if k in valid_keys}
        return AIMessage(**filtered)

    def _convert_chat_message_to_simple_format(
        self, chat_message, thread_id: str, session_id: str | None
    ) -> Dict[str, Any]:
        content: Dict[str, Any] = {
            "type": chat_message.type,
            "content": chat_message.content,
        }

        if chat_message.tool_calls:
            content["tool_calls"] = [
                {**tc, "name": tc["args"]["subagent_type"]}
                if tc.get("name") == "task" and "subagent_type" in tc.get("args", {})
                else tc
                for tc in chat_message.tool_calls
            ]
        if chat_message.tool_call_id:
            content["tool_call_id"] = chat_message.tool_call_id
        if chat_message.run_id:
            content["run_id"] = chat_message.run_id
        if thread_id:
            content["thread_id"] = thread_id
        if session_id:
            content["session_id"] = session_id
        if chat_message.ai_call_id:
            content["ai_call_id"] = chat_message.ai_call_id
        if chat_message.response_metadata:
            content["response_metadata"] = chat_message.response_metadata
        if chat_message.custom_data:
            content["custom_data"] = chat_message.custom_data

        return content

    def _update_tool_call_tracking(self, stream_mode: str, event: Any) -> None:
        try:
            if stream_mode == "updates":
                for node, updates in event.items():
                    if updates and "messages" in updates:
                        for message in updates["messages"]:
                            if hasattr(message, "tool_calls") and message.tool_calls:
                                self._current_tool_call_id = message.tool_calls[0].get("id")
                                return
            elif stream_mode == "messages":
                msg, metadata = event
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    self._current_tool_call_id = msg.tool_calls[0].get("id")
        except Exception:
            pass
