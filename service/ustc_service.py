import argparse
import json
import os
import sys
import time

from flask import Flask, Response, g, jsonify, request

from ustc_common import check_token_details, request_chat


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


MODELS = {
    "deepseek-r1": {
        "upstream": "deepseek",
        "show": "USTC Deepseek r1",
        "reasoning": True,
        "allow_tools": False,
        "aliases": ["deepseek", "__ustc_adapter__deepseek-r1"],
    },
    "deepseek-v3": {
        "upstream": "deepseek-v3",
        "show": "USTC Deepseek v3",
        "reasoning": False,
        "allow_tools": True,
        "aliases": ["__ustc_adapter__deepseek-v3"],
    },
}


def load_runtime_state(state_path):
    if not state_path or not os.path.exists(state_path):
        return {"ustcToken": "", "apiKeys": []}

    with open(state_path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def save_runtime_state(state_path, state):
    if not state_path:
        return

    with open(state_path, "w", encoding="utf-8") as handle:
        json.dump(state, handle, ensure_ascii=False, indent=2)


def extract_local_api_key():
    authorization = request.headers.get("Authorization", "")
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()

    return request.headers.get("x-api-key", "").strip()


def get_active_api_keys(state):
    return [item for item in state.get("apiKeys", []) if str(item.get("value", "")).strip()]


def validate_local_api_key(state):
    active_keys = get_active_api_keys(state)
    if not active_keys:
        return True, None

    presented = extract_local_api_key()
    if not presented:
        return False, "缺少本地 API Key。"

    now = int(time.time() * 1000)
    for item in active_keys:
        if str(item.get("value")) != presented:
            continue

        expires_at = item.get("expiresAt")
        if expires_at not in (None, "", 0) and now > int(expires_at):
            return False, "本地 API Key 已过期。"

        max_usage = int(item.get("maxUsage", -1))
        usage_count = int(item.get("usageCount", 0))
        if max_usage != -1 and usage_count >= max_usage:
            return False, "本地 API Key 已超过调用次数限制。"

        return True, item

    return False, "本地 API Key 无效。"


def consume_local_api_key(state_path, state, matched_key):
    if not matched_key:
        return

    matched_id = str(matched_key.get("id"))
    for item in state.get("apiKeys", []):
        if str(item.get("id")) == matched_id:
            item["usageCount"] = int(item.get("usageCount", 0)) + 1
            break

    save_runtime_state(state_path, state)


def openai_error(message, status_code, error_type="invalid_request_error"):
    return (
        jsonify(
            {
                "error": {
                    "message": message,
                    "type": error_type,
                    "param": None,
                    "code": None,
                }
            }
        ),
        status_code,
    )


def claude_error(message, status_code, error_type="invalid_request_error"):
    return (
        jsonify(
            {
                "type": "error",
                "error": {
                    "type": error_type,
                    "message": message,
                },
            }
        ),
        status_code,
    )


def extract_model_identifier(model_name):
    if isinstance(model_name, dict):
        for key in ("id", "name", "model", "slug"):
            if model_name.get(key):
                return extract_model_identifier(model_name.get(key))
        return ""

    return str(model_name or "").strip()


def iter_model_candidates(model_name):
    raw = extract_model_identifier(model_name)
    if not raw:
        return []

    variants = {raw, raw.lower()}
    normalized = raw.replace("\\", "/").strip()
    variants.add(normalized)
    variants.add(normalized.lower())

    # Accept provider-prefixed names such as "openai/deepseek-v3" or "ustc:deepseek-v3".
    separators = ["/", ":"]
    pending = list(variants)
    for value in pending:
        for separator in separators:
            if separator in value:
                tail = value.rsplit(separator, 1)[-1].strip()
                if tail:
                    variants.add(tail)
                    variants.add(tail.lower())

    return [item for item in variants if item]


def normalize_model_name(model_name):
    candidates = iter_model_candidates(model_name)
    if not candidates:
        return None

    for model_id, meta in MODELS.items():
        aliases = {
            model_id,
            model_id.lower(),
            str(meta.get("upstream", "")).strip(),
            str(meta.get("upstream", "")).strip().lower(),
        }
        aliases.update(str(alias).strip() for alias in meta.get("aliases", []))
        aliases.update(str(alias).strip().lower() for alias in meta.get("aliases", []))
        aliases = {alias for alias in aliases if alias}

        for candidate in candidates:
            normalized_candidate = candidate.strip()
            lowered_candidate = normalized_candidate.lower()
            if normalized_candidate in aliases or lowered_candidate in aliases:
                return model_id

    return None


def get_default_model_name(state):
    selected_model = normalize_model_name(state.get("selectedModel"))
    if selected_model:
        return selected_model

    return next(iter(MODELS.keys()), None)


def build_model_metadata(model_id, meta):
    return {
        "id": model_id,
        "name": meta["show"],
        "object": "model",
        "created": 0,
        "owned_by": "ustc",
        "permission": [],
        "root": model_id,
        "parent": None,
        "show": meta["show"],
        "supports_reasoning": bool(meta.get("reasoning")),
        "supports_tools": bool(meta.get("allow_tools")),
        "capabilities": {
            "input": ["text"],
            "output": ["text"],
            "tools": bool(meta.get("allow_tools")),
            "reasoning": bool(meta.get("reasoning")),
            "streaming": True,
        },
        "context_window": 128000,
        "max_output_tokens": 32768,
    }


def is_public_metadata_request():
    if request.method != "GET":
        return False

    return (
        request.path == "/v1/models"
        or request.path.startswith("/v1/models/")
        or request.path == "/v1/adapters"
        or request.path == "/models"
        or request.path.startswith("/models/")
    )


def stream_openai_response(upstream_response):
    try:
        for line in upstream_response.iter_lines(chunk_size=1, decode_unicode=True):
            if not line:
                continue

            if line.startswith("data: "):
                yield f"data: {line[6:]}\n\n"
                continue

            if line.strip() == "[DONE]":
                yield "data: [DONE]\n\n"
                return
    finally:
        upstream_response.close()


def collect_openai_response(upstream_response, model_name):
    try:
        answer_id = ""
        answer = ""
        tool_calls = {}
        finish_reason = "stop"

        for line in upstream_response.iter_lines(chunk_size=1, decode_unicode=True):
            if not line or not line.startswith("data: "):
                continue

            payload = line[6:]
            if payload.strip() == "[DONE]":
                break

            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                continue

            if "id" in data:
                answer_id = data.get("id", "")

            if data.get("object") != "chat.completion.chunk":
                continue

            choice = data.get("choices", [{}])[0]
            delta = choice.get("delta", {})
            finish_reason = choice.get("finish_reason") or finish_reason

            if "content" in delta:
                answer += delta["content"]

            if "tool_calls" in delta:
                for tool_call in delta["tool_calls"]:
                    index = tool_call.get("index", 0)
                    if index not in tool_calls:
                        tool_calls[index] = {
                            "id": tool_call.get("id"),
                            "type": tool_call.get("type"),
                            "function": {
                                "name": tool_call.get("function", {}).get("name", ""),
                                "arguments": "",
                            },
                        }

                    function_data = tool_call.get("function", {})
                    if "arguments" in function_data:
                        tool_calls[index]["function"]["arguments"] += function_data["arguments"]

        final_tool_calls = [tool_calls[index] for index in sorted(tool_calls.keys())]
        message = {"role": "assistant", "content": answer}
        if final_tool_calls:
            message["tool_calls"] = final_tool_calls

        return {
            "id": answer_id,
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model_name,
            "choices": [
                {
                    "index": 0,
                    "message": message,
                    "finish_reason": "tool_calls" if final_tool_calls else finish_reason or "stop",
                }
            ],
        }
    finally:
        upstream_response.close()


def claude_to_openai_messages(claude_messages, system=None):
    openai_messages = []
    if system:
        openai_messages.append({"role": "system", "content": system})

    for message in claude_messages:
        role = message["role"]
        content = message["content"]

        if isinstance(content, str):
            openai_messages.append({"role": role, "content": content})
            continue

        if not isinstance(content, list):
            continue

        if role == "user":
            for block in content:
                if block["type"] == "text":
                    openai_messages.append({"role": "user", "content": block["text"]})
                elif block["type"] == "tool_result":
                    tool_content = block["content"]
                    if not isinstance(tool_content, str):
                        tool_content = json.dumps(tool_content)
                    openai_messages.append(
                        {
                            "role": "tool",
                            "content": tool_content,
                            "tool_call_id": block["tool_use_id"],
                        }
                    )
            continue

        if role == "assistant":
            assistant_content = ""
            tool_calls = []
            for block in content:
                if block["type"] == "text":
                    assistant_content += block["text"]
                elif block["type"] == "tool_use":
                    tool_calls.append(
                        {
                            "id": block["id"],
                            "type": "function",
                            "function": {
                                "name": block["name"],
                                "arguments": json.dumps(block["input"]),
                            },
                        }
                    )

            payload = {"role": "assistant"}
            if assistant_content:
                payload["content"] = assistant_content
            if tool_calls:
                payload["tool_calls"] = tool_calls
            openai_messages.append(payload)

    return openai_messages


def claude_to_openai_tools(claude_tools):
    openai_tools = []
    for tool in claude_tools:
        openai_tools.append(
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("input_schema", {}),
                },
            }
        )

    return openai_tools


def stringify_response_value(value):
    if value is None:
        return ""

    if isinstance(value, str):
        return value

    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)

    return str(value)


def extract_response_text(content):
    if content is None:
        return ""

    if isinstance(content, str):
        return content

    if not isinstance(content, list):
        return stringify_response_value(content)

    text_parts = []
    for block in content:
        if isinstance(block, str):
            text_parts.append(block)
            continue

        if not isinstance(block, dict):
            text_parts.append(stringify_response_value(block))
            continue

        block_type = block.get("type")
        if block_type in ("input_text", "output_text", "text", "summary_text"):
            text_parts.append(str(block.get("text", "")))
            continue

        if block_type == "refusal":
            text_parts.append(str(block.get("refusal", "")))
            continue

        if "text" in block:
            text_parts.append(str(block.get("text", "")))

    return "".join(text_parts)


def responses_to_openai_messages(response_input, instructions=None):
    openai_messages = []
    if instructions:
        openai_messages.append({"role": "system", "content": instructions})

    if response_input is None:
        return openai_messages

    if isinstance(response_input, str):
        openai_messages.append({"role": "user", "content": response_input})
        return openai_messages

    if not isinstance(response_input, list):
        openai_messages.append({"role": "user", "content": stringify_response_value(response_input)})
        return openai_messages

    for item in response_input:
        if isinstance(item, str):
            openai_messages.append({"role": "user", "content": item})
            continue

        if not isinstance(item, dict):
            continue

        item_type = item.get("type")
        if item_type in (None, "message"):
            role = item.get("role", "user")
            message_payload = {"role": role}
            content_text = extract_response_text(item.get("content"))
            if content_text or role != "assistant":
                message_payload["content"] = content_text

            if message_payload.get("content") or message_payload.get("tool_calls"):
                openai_messages.append(message_payload)
            continue

        if item_type == "function_call":
            call_id = item.get("call_id") or item.get("id") or f"call_{len(openai_messages)}"
            arguments = item.get("arguments")
            if arguments is None and "input" in item:
                arguments = json.dumps(item.get("input", {}), ensure_ascii=False)

            openai_messages.append(
                {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": call_id,
                            "type": "function",
                            "function": {
                                "name": item.get("name", "function"),
                                "arguments": stringify_response_value(arguments),
                            },
                        }
                    ],
                }
            )
            continue

        if item_type == "function_call_output":
            call_id = item.get("call_id") or item.get("tool_call_id") or item.get("id") or f"call_{len(openai_messages)}"
            openai_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": stringify_response_value(item.get("output")),
                }
            )
            continue

        if item_type in ("reasoning", "item_reference"):
            continue

        role = item.get("role")
        if role:
            content_text = extract_response_text(item.get("content"))
            if content_text:
                openai_messages.append({"role": role, "content": content_text})

    return openai_messages


def responses_to_openai_tools(response_tools):
    openai_tools = []
    for tool in response_tools or []:
        if not isinstance(tool, dict) or tool.get("type") != "function":
            continue

        function_payload = tool.get("function") if isinstance(tool.get("function"), dict) else tool
        name = function_payload.get("name")
        if not name:
            continue

        openai_tools.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": function_payload.get("description", ""),
                    "parameters": function_payload.get("parameters", {}),
                },
            }
        )

    return openai_tools


def resolve_response_input(data):
    if not isinstance(data, dict):
        return None

    for key in ("input", "messages", "prompt", "text"):
        if key in data and data.get(key) is not None:
            return data.get(key)

    if data.get("instructions"):
        return []

    return None


def ensure_response_messages(messages, previous_messages=None):
    if messages or previous_messages:
        return messages

    # Codex may probe /v1/responses with an empty input payload.
    return [{"role": "user", "content": ""}]


def build_responses_usage(usage=None):
    usage = usage or {}
    input_tokens = int(usage.get("input_tokens", usage.get("prompt_tokens", 0)) or 0)
    output_tokens = int(usage.get("output_tokens", usage.get("completion_tokens", 0)) or 0)
    total_tokens = int(usage.get("total_tokens", input_tokens + output_tokens) or 0)

    return {
        "input_tokens": input_tokens,
        "input_tokens_details": {
            "cached_tokens": int(usage.get("cached_tokens", 0) or 0),
        },
        "output_tokens": output_tokens,
        "output_tokens_details": {
            "reasoning_tokens": int(usage.get("reasoning_tokens", 0) or 0),
        },
        "total_tokens": total_tokens,
    }


def build_responses_payload(response_id, model_name, output, instructions=None, status="completed", usage=None, created_at=None, input_items=None):
    timestamp = created_at or int(time.time())
    completed_at = timestamp if status in ("completed", "failed", "incomplete") else None
    return {
        "id": response_id,
        "object": "response",
        "created_at": timestamp,
        "status": status,
        "completed_at": completed_at,
        "error": None,
        "incomplete_details": None,
        "input": input_items if input_items is not None else [],
        "instructions": instructions,
        "max_output_tokens": None,
        "model": model_name,
        "output": output,
        "parallel_tool_calls": True,
        "previous_response_id": None,
        "reasoning_effort": None,
        "reasoning": {
            "effort": None,
            "summary": None,
        },
        "store": False,
        "temperature": 1,
        "text": {
            "format": {
                "type": "text",
            }
        },
        "tool_choice": "auto",
        "tools": [],
        "top_p": 1,
        "truncation": "disabled",
        "usage": build_responses_usage(usage) if status == "completed" else None,
        "user": None,
        "metadata": {},
    }


def openai_to_responses_output(openai_response):
    response_id = openai_response.get("id") or f"resp_{int(time.time() * 1000)}"
    choice = openai_response.get("choices", [{}])[0]
    message = choice.get("message", {})
    output = []

    content = message.get("content")
    if content:
        output.append(
            {
                "id": f"msg_{response_id}",
                "type": "message",
                "status": "completed",
                "role": "assistant",
                "content": [
                    {
                        "type": "output_text",
                        "text": content,
                        "annotations": [],
                    }
                ],
            }
        )

    for tool_call in message.get("tool_calls", []):
        call_id = tool_call.get("id") or f"call_{len(output)}"
        output.append(
            {
                "id": f"fc_{call_id}",
                "type": "function_call",
                "status": "completed",
                "call_id": call_id,
                "name": tool_call.get("function", {}).get("name", "function"),
                "arguments": tool_call.get("function", {}).get("arguments", ""),
            }
        )

    return response_id, output


def openai_response_to_messages(openai_response):
    choice = openai_response.get("choices", [{}])[0]
    message = choice.get("message", {})
    assistant_message = {"role": "assistant"}

    if message.get("content"):
        assistant_message["content"] = message["content"]

    if message.get("tool_calls"):
        assistant_message["tool_calls"] = message["tool_calls"]

    if assistant_message.get("content") or assistant_message.get("tool_calls"):
        return [assistant_message]

    return []


def responses_event(event_type, sequence_number=None, **payload):
    body = {"type": event_type}
    body.update(payload)
    if sequence_number is not None:
        body["sequence_number"] = sequence_number
    return f"event: {event_type}\ndata: {json.dumps(body, ensure_ascii=False)}\n\n"


def build_responses_assistant_message(message_output_index, message_item_id, text_segments, tool_states):
    final_output = []

    if message_output_index is not None:
        text_content = "".join(text_segments)
        content_part = {
            "type": "output_text",
            "text": text_content,
            "annotations": [],
        }
        final_message_item = {
            "id": message_item_id,
            "type": "message",
            "status": "completed",
            "role": "assistant",
            "content": [content_part],
        }
        final_output.append((message_output_index, final_message_item))

    for tool_state in sorted(tool_states.values(), key=lambda item: item["output_index"]):
        final_tool_item = {
            "id": tool_state["item_id"],
            "type": "function_call",
            "status": "completed",
            "call_id": tool_state["call_id"],
            "name": tool_state["name"],
            "arguments": tool_state["arguments"],
        }
        final_output.append((tool_state["output_index"], final_tool_item))

    final_output.sort(key=lambda item: item[0])
    return final_output


def create_app(state_path):
    app = Flask(__name__)

    @app.after_request
    def attach_cors_headers(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type, X-API-Key, anthropic-version"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        return response

    @app.before_request
    def ensure_local_api_key():
        if request.method == "OPTIONS":
            return ("", 204)

        if not request.path.startswith("/v1/"):
            return None

        if is_public_metadata_request():
            return None

        state = load_runtime_state(state_path)
        allowed, matched_key_or_message = validate_local_api_key(state)
        if not allowed:
            if request.path == "/v1/messages":
                return claude_error(matched_key_or_message, 401, "authentication_error")
            return openai_error(matched_key_or_message, 401, "authentication_error")

        g.runtime_state = state
        g.runtime_api_key = matched_key_or_message
        return None

    @app.get("/")
    def home():
        return jsonify({"service": "fkunichat-ustc", "status": "ok"})

    @app.get("/health")
    def health():
        state = load_runtime_state(state_path)
        token = state.get("ustcToken", "")
        token_details = check_token_details(token) if token else {
            "valid": False,
            "reason": "missing_token",
            "statusCode": None,
            "contentType": "",
            "bodyPreview": "",
        }
        return jsonify(
            {
                "ok": True,
                "tokenConfigured": bool(token),
                "tokenValid": token_details["valid"],
                "tokenReason": token_details["reason"],
                "tokenStatusCode": token_details["statusCode"],
                "tokenContentType": token_details["contentType"],
                "tokenBodyPreview": token_details["bodyPreview"],
            }
        )

    @app.get("/v1/adapters")
    def list_adapters():
        return jsonify(
            {
                "object": "list",
                "data": [
                    {
                        "id": "ustc",
                        "object": "adapter",
                        "created": None,
                        "owned_by": "USTC",
                        "permission": [],
                        "root": "ustc",
                        "parent": None,
                    }
                ],
            }
        )

    @app.get("/models")
    @app.get("/v1/models")
    def list_models():
        return jsonify(
            {
                "object": "list",
                "data": [build_model_metadata(model_id, meta) for model_id, meta in MODELS.items()],
            }
        )

    @app.get("/models/<path:model_name>")
    @app.get("/v1/models/<path:model_name>")
    def get_model(model_name):
        normalized = normalize_model_name(model_name)
        if not normalized:
            return openai_error("模型不存在。", 404)

        return jsonify(build_model_metadata(normalized, MODELS[normalized]))

    @app.post("/v1/chat/completions")
    def chat_completions():
        state = getattr(g, "runtime_state", load_runtime_state(state_path))
        token = state.get("ustcToken", "")
        if not token:
            return openai_error("USTChat Token 未配置。", 503, "authentication_error")

        data = request.get_json(force=True, silent=True) or {}
        stream = bool(data.get("stream", False))
        with_search = bool(data.get("with_search", False))
        model_name = normalize_model_name(data.get("model")) or get_default_model_name(state)
        messages = data.get("messages", [])
        tools = data.get("tools", [])

        if not model_name:
            return openai_error("模型不存在。", 400)

        try:
            upstream_response = request_chat(
                token,
                MODELS[model_name]["upstream"],
                messages,
                stream=stream,
                with_search=with_search,
                tools=tools if MODELS[model_name]["allow_tools"] else [],
            )

            if upstream_response.status_code == 401:
                return openai_error("USTChat Token 无效。", 401, "authentication_error")
            if upstream_response.status_code != 200:
                return openai_error(
                    f"USTC 请求失败: {upstream_response.status_code} {upstream_response.text}",
                    502,
                    "server_error",
                )

            consume_local_api_key(state_path, state, getattr(g, "runtime_api_key", None))

            if stream:
                return Response(
                    stream_openai_response(upstream_response),
                    content_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "X-Accel-Buffering": "no",
                    },
                )

            return jsonify(collect_openai_response(upstream_response, model_name))
        except Exception as exc:
            return openai_error(str(exc), 500, "server_error")

    @app.post("/v1/responses")
    def responses():
        return openai_error("/v1/responses 暂不支持。请使用 /v1/chat/completions。", 404, "invalid_request_error")

    @app.post("/v1/messages")
    def messages():
        state = getattr(g, "runtime_state", load_runtime_state(state_path))
        token = state.get("ustcToken", "")
        if not token:
            return claude_error("USTChat Token 未配置。", 503, "authentication_error")

        data = request.get_json(force=True, silent=True) or {}
        model_name = normalize_model_name(data.get("model")) or get_default_model_name(state)
        if not model_name:
            return claude_error("模型不存在。", 400)

        claude_messages = data.get("messages")
        if not claude_messages:
            return claude_error("messages is required", 400)

        if data.get("max_tokens") is None:
            return claude_error("max_tokens is required", 400)

        stream = bool(data.get("stream", False))
        with_search = bool(data.get("with_search", False))
        openai_messages = claude_to_openai_messages(claude_messages, data.get("system"))
        openai_tools = claude_to_openai_tools(data.get("tools", []))

        try:
            upstream_response = request_chat(
                token,
                MODELS[model_name]["upstream"],
                openai_messages,
                stream=stream,
                with_search=with_search,
                tools=openai_tools if MODELS[model_name]["allow_tools"] else [],
            )

            if upstream_response.status_code == 401:
                return claude_error("USTChat Token 无效。", 401, "authentication_error")
            if upstream_response.status_code != 200:
                return claude_error(
                    f"USTC 请求失败: {upstream_response.status_code} {upstream_response.text}",
                    502,
                    "server_error",
                )

            consume_local_api_key(state_path, state, getattr(g, "runtime_api_key", None))

            if stream:
                def transform_stream():
                    try:
                        yield "event: message_start\n"
                        yield (
                            f'data: {{"type":"message_start","message":{{"id":"msg_1","type":"message",'
                            f'"role":"assistant","content":[],"model":"{model_name}","stop_reason":null,'
                            '"stop_sequence":null,"usage":{"input_tokens":0,"output_tokens":0}}}}\n\n'
                        )

                        content_index = 0
                        tool_indices = {}
                        partial_output_tokens = 0
                        saw_text = False
                        stop_reason = None

                        for line in stream_openai_response(upstream_response):
                            if not line.startswith("data: "):
                                continue

                            payload = line[6:].strip()
                            if payload == "[DONE]":
                                break

                            try:
                                chunk = json.loads(payload)
                            except json.JSONDecodeError:
                                continue

                            if "choices" not in chunk or not chunk["choices"]:
                                continue

                            delta = chunk["choices"][0]["delta"]

                            if "content" in delta and delta["content"] is not None:
                                text = delta["content"]
                                if not saw_text:
                                    saw_text = True
                                    yield "event: content_block_start\n"
                                    yield (
                                        f'data: {{"type":"content_block_start","index":{content_index},'
                                        '"content_block":{"type":"text","text":""}}}\n\n'
                                    )
                                    content_index += 1
                                yield "event: content_block_delta\n"
                                yield (
                                    f'data: {{"type":"content_block_delta","index":{content_index - 1},'
                                    f'"delta":{{"type":"text_delta","text":{json.dumps(text)}}}}}\n\n'
                                )
                                partial_output_tokens += len(text.split())

                            if "tool_calls" in delta and delta["tool_calls"]:
                                for tool_call in delta["tool_calls"]:
                                    index = tool_call["index"]
                                    if index not in tool_indices:
                                        tool_indices[index] = content_index
                                        content_index += 1
                                        tool_id = tool_call.get("id", f"toolu_{index}")
                                        tool_name = tool_call.get("function", {}).get("name", "unknown")
                                        yield "event: content_block_start\n"
                                        yield (
                                            f'data: {{"type":"content_block_start","index":{tool_indices[index]},'
                                            f'"content_block":{{"type":"tool_use","id":"{tool_id}",'
                                            f'"name":"{tool_name}","input":{{}}}}}}\n\n'
                                        )

                                    arguments = tool_call.get("function", {}).get("arguments")
                                    if arguments:
                                        yield "event: content_block_delta\n"
                                        yield (
                                            f'data: {{"type":"content_block_delta","index":{tool_indices[index]},'
                                            f'"delta":{{"type":"input_json_delta","partial_json":{json.dumps(arguments)}}}}}\n\n'
                                        )
                                        partial_output_tokens += len(arguments.split())

                            if chunk["choices"][0].get("finish_reason"):
                                stop_reason = chunk["choices"][0]["finish_reason"]

                        for index in range(content_index):
                            yield "event: content_block_stop\n"
                            yield f'data: {{"type":"content_block_stop","index":{index}}}\n\n'

                        normalized_stop_reason = (
                            "tool_use" if stop_reason == "tool_calls" else "end_turn"
                        )
                        yield "event: message_delta\n"
                        yield (
                            f'data: {{"type":"message_delta","delta":{{"stop_reason":"{normalized_stop_reason}",'
                            f'"stop_sequence":null}},"usage":{{"output_tokens":{partial_output_tokens}}}}}\n\n'
                        )
                        yield "event: message_stop\n"
                        yield 'data: {"type":"message_stop"}\n\n'
                    finally:
                        upstream_response.close()

                return Response(
                    transform_stream(),
                    content_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "X-Accel-Buffering": "no",
                    },
                )

            openai_response = collect_openai_response(upstream_response, model_name)
            choice = openai_response["choices"][0]
            message = choice["message"]
            content_blocks = []

            if message.get("content"):
                content_blocks.append({"type": "text", "text": message["content"]})

            if "tool_calls" in message:
                for tool_call in message["tool_calls"]:
                    content_blocks.append(
                        {
                            "type": "tool_use",
                            "id": tool_call["id"],
                            "name": tool_call["function"]["name"],
                            "input": json.loads(tool_call["function"]["arguments"]),
                        }
                    )

            stop_reason = "tool_use" if choice["finish_reason"] == "tool_calls" else "end_turn"
            return jsonify(
                {
                    "id": openai_response.get("id", "msg_1"),
                    "type": "message",
                    "role": "assistant",
                    "model": model_name,
                    "content": content_blocks,
                    "stop_reason": stop_reason,
                    "stop_sequence": None,
                    "usage": openai_response.get("usage", {"input_tokens": 0, "output_tokens": 0}),
                }
            )
        except Exception as exc:
            return claude_error(str(exc), 500, "server_error")

    return app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=28080)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--state-file", required=True)
    args = parser.parse_args()

    app = create_app(args.state_file)
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
