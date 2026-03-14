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
    },
    "deepseek-v3": {
        "upstream": "deepseek-v3",
        "show": "USTC Deepseek v3",
        "reasoning": False,
        "allow_tools": True,
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


def normalize_model_name(model_name):
    if model_name in MODELS:
        return model_name

    lowered = str(model_name or "").lower()
    for model_id in MODELS:
        if model_id.lower() == lowered:
            return model_id

    return None


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

    @app.get("/v1/models")
    def list_models():
        return jsonify(
            {
                "object": "list",
                "data": [
                    {
                        "id": model_id,
                        "show": meta["show"],
                        "object": "model",
                        "created": None,
                        "owned_by": "ustc",
                        "permission": [],
                        "root": model_id,
                        "parent": None,
                    }
                    for model_id, meta in MODELS.items()
                ],
            }
        )

    @app.post("/v1/chat/completions")
    def chat_completions():
        state = getattr(g, "runtime_state", load_runtime_state(state_path))
        token = state.get("ustcToken", "")
        if not token:
            return openai_error("USTChat Token 未配置。", 503, "authentication_error")

        data = request.get_json(force=True, silent=True) or {}
        stream = bool(data.get("stream", False))
        with_search = bool(data.get("with_search", False))
        model_name = normalize_model_name(data.get("model"))
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

    @app.post("/v1/messages")
    def messages():
        state = getattr(g, "runtime_state", load_runtime_state(state_path))
        token = state.get("ustcToken", "")
        if not token:
            return claude_error("USTChat Token 未配置。", 503, "authentication_error")

        data = request.get_json(force=True, silent=True) or {}
        model_name = normalize_model_name(data.get("model"))
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
