import json
import os
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone


ALAPI_TOKEN = os.getenv("ALAPI_TOKEN", "").strip()
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK", "").strip()

ALAPI_URL = "https://v2.alapi.cn/api/zaobao"
HN_RSS_URL = "https://hnrss.org/frontpage"

BJT = timezone(timedelta(hours=8))


def http_get_json(url, params=None, timeout=20):
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "daily-news-bot/1.0",
            "Accept": "application/json",
        },
    )

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
        return json.loads(body)


def http_get_text(url, timeout=20):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "daily-news-bot/1.0",
            "Accept": "application/rss+xml, application/xml, text/xml",
        },
    )

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def post_json(url, payload, timeout=20):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "daily-news-bot/1.0",
        },
    )

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", errors="replace")
        return resp.status, body


def clean_html(text):
    if not text:
        return ""

    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&quot;", '"')
    text = text.replace("&#39;", "'")
    return re.sub(r"\s+", " ", text).strip()


def fetch_alapi_morning_news():
    if not ALAPI_TOKEN:
        raise RuntimeError("Missing ALAPI_TOKEN")

    data = http_get_json(
        ALAPI_URL,
        params={
            "token": ALAPI_TOKEN,
            "format": "json",
        },
    )

    if str(data.get("code")) not in {"200", "0"}:
        raise RuntimeError(f"ALAPI request failed: {data}")

    payload = data.get("data") or {}

    news = []
    raw_news = payload.get("news") or payload.get("zaobao") or []

    if isinstance(raw_news, str):
        raw_news = [line.strip() for line in raw_news.splitlines() if line.strip()]

    if isinstance(raw_news, list):
        for item in raw_news:
            if isinstance(item, str):
                title = item.strip()
            elif isinstance(item, dict):
                title = (
                    item.get("title")
                    or item.get("content")
                    or item.get("text")
                    or ""
                ).strip()
            else:
                title = ""

            if title:
                news.append(title)

    if not news:
        raw_text = payload.get("content") or payload.get("text") or ""
        if raw_text:
            news = [line.strip() for line in raw_text.splitlines() if line.strip()]

    return news[:12]


def fetch_hacker_news_ai_items():
    rss_text = http_get_text(HN_RSS_URL)
    root = ET.fromstring(rss_text)

    channel = root.find("channel")
    if channel is None:
        return []

    keywords = [
        "ai",
        "artificial intelligence",
        "llm",
        "large language model",
        "openai",
        "anthropic",
        "claude",
        "gemini",
        "deepmind",
        "machine learning",
        "ml",
        "neural",
        "agent",
        "rag",
        "transformer",
        "gpu",
        "nvidia",
        "inference",
        "model",
    ]

    items = []

    for item in channel.findall("item"):
        title = clean_html(item.findtext("title", default=""))
        link = clean_html(item.findtext("link", default=""))
        description = clean_html(item.findtext("description", default=""))

        haystack = f"{title} {description}".lower()
        if any(keyword in haystack for keyword in keywords):
            items.append(
                {
                    "title": title,
                    "link": link,
                }
            )

    if len(items) < 5:
        for item in channel.findall("item"):
            title = clean_html(item.findtext("title", default=""))
            link = clean_html(item.findtext("link", default=""))

            if title and all(existing["title"] != title for existing in items):
                items.append(
                    {
                        "title": title,
                        "link": link,
                    }
                )

            if len(items) >= 5:
                break

    return items[:8]


def build_message(world_news, ai_items):
    today = datetime.now(BJT).strftime("%Y-%m-%d")

    lines = [
        f"🗞️ 每日新闻早报｜{today}",
        "",
        "🌍 今日世界要闻",
    ]

    if world_news:
        for index, item in enumerate(world_news, start=1):
            lines.append(f"{index}. {item}")
    else:
        lines.append("暂无可用要闻。")

    lines.extend(
        [
            "",
            "🤖 AI 专递",
        ]
    )

    if ai_items:
        for index, item in enumerate(ai_items, start=1):
            title = item["title"]
            link = item["link"]
            lines.append(f"{index}. {title}")
            if link:
                lines.append(f"   {link}")
    else:
        lines.append("暂无 AI 新闻。")

    lines.extend(
        [
            "",
            "——",
            "来源：ALAPI 早报 + Hacker News RSS",
        ]
    )

    return "\n".join(lines)


def send_to_feishu(text):
    if not FEISHU_WEBHOOK:
        raise RuntimeError("Missing FEISHU_WEBHOOK")

    payload = {
        "msg_type": "text",
        "content": {
            "text": text,
        },
    }

    status, body = post_json(FEISHU_WEBHOOK, payload)

    if status < 200 or status >= 300:
        raise RuntimeError(f"Feishu webhook failed: HTTP {status}, {body}")

    try:
        result = json.loads(body)
    except json.JSONDecodeError:
        result = {}

    if result.get("code") not in (None, 0):
        raise RuntimeError(f"Feishu webhook returned error: {body}")

    return body


def main():
    errors = []

    try:
        world_news = fetch_alapi_morning_news()
    except Exception as exc:
        world_news = []
        errors.append(f"ALAPI 获取失败：{exc}")

    try:
        ai_items = fetch_hacker_news_ai_items()
    except Exception as exc:
        ai_items = []
        errors.append(f"Hacker News RSS 获取失败：{exc}")

    message = build_message(world_news, ai_items)

    if errors:
        message += "\n\n⚠️ 数据源提醒\n" + "\n".join(f"- {error}" for error in errors)

    print(message)

    send_to_feishu(message)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
