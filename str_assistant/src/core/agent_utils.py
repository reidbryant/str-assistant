"""Utility functions for message conversion in the STR Assistant."""

from typing import Any, Dict, List, Union

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.messages import ChatMessage as LangchainChatMessage

from str_assistant.src.schema import ChatMessage, ToolCall


def convert_message_content_to_string(
    content: Union[str, List[Union[str, Dict[str, Any]]]],
) -> str:
    if isinstance(content, str):
        return content

    text: List[str] = []
    for content_item in content:
        if isinstance(content_item, str):
            text.append(content_item)
            continue
        if content_item.get("type") == "text":
            text.append(content_item["text"])
    return "".join(text)


def langchain_to_chat_message(message: BaseMessage) -> ChatMessage:
    match message:
        case HumanMessage():
            return ChatMessage(
                type="human",
                content=convert_message_content_to_string(message.content),
            )

        case AIMessage():
            ai_message = ChatMessage(
                type="ai",
                content=convert_message_content_to_string(message.content),
            )
            tool_calls = message.tool_calls or []
            if message.additional_kwargs and "tool_calls" in message.additional_kwargs:
                tool_calls.extend(message.additional_kwargs["tool_calls"])

            if tool_calls:
                formatted_tool_calls = []
                for tool_call in tool_calls:
                    if isinstance(tool_call, dict) and "name" in tool_call and "args" in tool_call:
                        formatted_call: ToolCall = {
                            "name": str(tool_call["name"]),
                            "args": dict(tool_call["args"]),
                            "id": str(tool_call.get("id")) if tool_call.get("id") else None,
                            "type": "tool_call",
                        }
                        formatted_tool_calls.append(formatted_call)
                ai_message.tool_calls = formatted_tool_calls

            if message.response_metadata:
                ai_message.response_metadata = message.response_metadata
            return ai_message

        case ToolMessage():
            return ChatMessage(
                type="tool",
                content=convert_message_content_to_string(message.content),
                tool_call_id=message.tool_call_id,
            )

        case LangchainChatMessage():
            if message.role == "custom":
                return ChatMessage(
                    type="custom",
                    content="",
                    custom_data=message.content[0],
                )
            else:
                raise ValueError(f"Unsupported chat message role: {message.role}")

        case _:
            raise ValueError(f"Unsupported message type: {message.__class__.__name__}")


def remove_tool_calls(
    content: Union[str, List[Union[str, Dict[str, Any]]]],
) -> Union[str, List[Union[str, Dict[str, Any]]]]:
    if isinstance(content, str):
        return content
    return [
        content_item
        for content_item in content
        if isinstance(content_item, str) or content_item.get("type") != "tool_use"
    ]
