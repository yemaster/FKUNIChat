import random

import requests


BACKEND_URL = "https://chat.ustc.edu.cn"
LOGIN_URL = "https://id.ustc.edu.cn/cas/login?service=https:%2F%2Fchat.ustc.edu.cn%2Fustchat%2F"
CHAT_URL_PREFIX = "https://chat.ustc.edu.cn/ustchat"
STATIC_COOKIES = {
    "_ga_Q8WSZQS8E1": "GS2.1.s1757597943$o7$g0$t1757597943$j60$l0$h1338098571",
    "_ga": "GA1.1.1970297231.1750309927",
    "_ga_PG4WGSYP0Y": "GS2.1.s1758189290$o2$g1$t1758192312$j60$l0$h0",
    "_ga_HYDB8XD6M6": "GS2.1.s1758189297$o13$g1$t1758192312$j60$l0$h0",
}
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0"
)


def get_random_queue_code():
    chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"
    return "".join(random.choice(chars) for _ in range(32))


def build_headers(token, accept="application/json, text/plain, */*", include_json=True):
    headers = {
        "accept": accept,
        "accept-language": "zh-CN,zh-TW;q=0.9,zh;q=0.8,en;q=0.7,en-GB;q=0.6,en-US;q=0.5",
        "authorization": f"Bearer {token}",
        "dnt": "1",
        "origin": "https://chat.ustc.edu.cn",
        "priority": "u=1, i",
        "referer": "https://chat.ustc.edu.cn/ustchat/",
        "sec-ch-ua": '"Chromium";v="140", "Not=A?Brand";v="24", "Microsoft Edge";v="140"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": USER_AGENT,
    }

    if include_json:
        headers["content-type"] = "application/json"

    return headers


def check_token_details(token):
    if not token:
        return {
            "valid": False,
            "reason": "missing_token",
            "statusCode": None,
            "contentType": "",
            "bodyPreview": "",
        }

    try:
        response = requests.post(
            f"{BACKEND_URL}/ms-api/search-app",
            cookies=STATIC_COOKIES,
            headers=build_headers(token),
            json={"input": "帮我用 Python 解决这道题"},
            timeout=20,
        )
    except requests.RequestException as exc:
        return {
            "valid": False,
            "reason": "request_exception",
            "statusCode": None,
            "contentType": "",
            "bodyPreview": str(exc),
        }

    body_preview = (response.text or "")[:300]
    content_type = response.headers.get("content-type", "").lower()

    if response.status_code != 200:
        return {
            "valid": False,
            "reason": "unexpected_status",
            "statusCode": response.status_code,
            "contentType": content_type,
            "bodyPreview": body_preview,
        }

    if "application/json" not in content_type:
        return {
            "valid": False,
            "reason": "unexpected_content_type",
            "statusCode": response.status_code,
            "contentType": content_type,
            "bodyPreview": body_preview,
        }

    try:
        payload = response.json()
    except ValueError:
        return {
            "valid": False,
            "reason": "json_decode_failed",
            "statusCode": response.status_code,
            "contentType": content_type,
            "bodyPreview": body_preview,
        }

    if payload in (None, "", [], {}):
        return {
            "valid": False,
            "reason": "empty_payload",
            "statusCode": response.status_code,
            "contentType": content_type,
            "bodyPreview": body_preview,
        }

    if isinstance(payload, dict) and payload.get("code") in (401, 403):
        return {
            "valid": False,
            "reason": "payload_denied",
            "statusCode": response.status_code,
            "contentType": content_type,
            "bodyPreview": body_preview,
        }

    return {
        "valid": True,
        "reason": "ok",
        "statusCode": response.status_code,
        "contentType": content_type,
        "bodyPreview": body_preview,
    }


def is_token_valid(token):
    return check_token_details(token)["valid"]


def enter_queue(token):
    queue_code = get_random_queue_code()
    response = requests.get(
        f"{BACKEND_URL}/ms-api/mei-wei-bu-yong-deng",
        params={"queue_code": queue_code},
        cookies=STATIC_COOKIES,
        headers=build_headers(token, include_json=False),
        timeout=20,
    )
    response.raise_for_status()
    return queue_code


def request_chat(token, model, messages, stream=False, with_search=False, tools=None):
    queue_code = enter_queue(token)
    payload = {
      "messages": messages,
      "queue_code": queue_code,
      "model": model,
      "stream": bool(stream),
      "with_search": bool(with_search),
    }

    if tools:
        payload["tools"] = tools

    response = requests.post(
        f"{BACKEND_URL}/ms-api/chat-messages",
        cookies=STATIC_COOKIES,
        headers=build_headers(token, accept="text/event-stream, */*"),
        json=payload,
        stream=True,
    )
    return response
