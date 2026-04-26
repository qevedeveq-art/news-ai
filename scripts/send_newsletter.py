#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from html import unescape
from typing import Any


USER_AGENT = "news-ai-slack-bot/1.0"
TIMEOUT_SECONDS = 20
MAX_ITEMS_PER_SOURCE = 3

SOURCES = [
    {
        "id": "openai",
        "name": "OpenAI",
        "homepage": "https://openai.com/news/company-announcements/",
        "feeds": [
            "https://openai.com/news/rss.xml",
            "https://openai.com/blog/rss.xml",
        ],
    },
    {
        "id": "anthropic",
        "name": "Anthropic",
        "homepage": "https://www.anthropic.com/news",
        "feeds": [
            "https://www.anthropic.com/rss.xml",
            "https://www.anthropic.com/news/rss",
        ],
    },
    {
        "id": "google",
        "name": "Google / Gemini",
        "homepage": "https://blog.google/technology/ai/",
        "feeds": [
            "https://blog.google/technology/ai/rss/",
            "https://blog.google/rss/",
        ],
    },
]


def fetch_url(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return response.read()


def clean_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value or "")
    value = unescape(value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def parse_date(raw: str | None) -> dt.datetime | None:
    if not raw:
        return None
    try:
        parsed = parsedate_to_datetime(raw)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.astimezone(dt.timezone.utc)
    except Exception:
        pass
    for fmt in ("%b %d, %Y", "%B %d, %Y"):
        try:
            parsed = dt.datetime.strptime(raw, fmt)
            return parsed.replace(tzinfo=dt.timezone.utc)
        except ValueError:
            continue
    return None


def parse_feed(xml_bytes: bytes) -> list[dict[str, Any]]:
    root = ET.fromstring(xml_bytes)
    items: list[dict[str, Any]] = []

    for item in root.findall(".//item"):
        title = clean_text(item.findtext("title", default=""))
        link = (item.findtext("link", default="") or "").strip()
        description = clean_text(
            item.findtext("description", default="")
            or item.findtext("{http://purl.org/rss/1.0/modules/content/}encoded", default="")
        )
        published = parse_date(item.findtext("pubDate"))
        if title and link:
            items.append(
                {
                    "title": title,
                    "link": link,
                    "summary": description,
                    "published": published,
                }
            )

    for entry in root.findall(".//{http://www.w3.org/2005/Atom}entry"):
        ns = "{http://www.w3.org/2005/Atom}"
        title = clean_text(entry.findtext(f"{ns}title", default=""))
        link = ""
        for link_node in entry.findall(f"{ns}link"):
            href = (link_node.attrib.get("href") or "").strip()
            rel = (link_node.attrib.get("rel") or "alternate").strip()
            if href and rel == "alternate":
                link = href
                break
            if href and not link:
                link = href
        description = clean_text(
            entry.findtext(f"{ns}summary", default="")
            or entry.findtext(f"{ns}content", default="")
        )
        published = parse_date(
            entry.findtext(f"{ns}published", default="")
            or entry.findtext(f"{ns}updated", default="")
        )
        if title and link:
            items.append(
                {
                    "title": title,
                    "link": link,
                    "summary": description,
                    "published": published,
                }
            )

    return items


class AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.anchors: list[dict[str, str]] = []
        self._current_href: str | None = None
        self._text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        attrs_dict = dict(attrs)
        self._current_href = attrs_dict.get("href")
        self._text_parts = []

    def handle_data(self, data: str) -> None:
        if self._current_href is not None:
            self._text_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or self._current_href is None:
            return
        text = clean_text(" ".join(self._text_parts))
        self.anchors.append({"href": self._current_href, "text": text})
        self._current_href = None
        self._text_parts = []


def parse_openai_html(source: dict[str, Any], html_bytes: bytes) -> list[dict[str, Any]]:
    parser = AnchorParser()
    parser.feed(html_bytes.decode("utf-8", errors="ignore"))
    results: list[dict[str, Any]] = []
    seen_links: set[str] = set()
    pattern = re.compile(
        r"^(?P<title>.+?)\s+"
        r"(?P<category>Company|Research|Product|Safety|Engineering|Security|Global Affairs|AI Adoption)"
        r"\s+(?P<date>[A-Z][a-z]{2} \d{1,2}, \d{4})$"
    )
    for anchor in parser.anchors:
        href = anchor["href"].strip()
        if not href:
            continue
        absolute_url = urllib.parse.urljoin(source["homepage"], href)
        if "/index/" not in absolute_url and "/research/" not in absolute_url:
            continue
        match = pattern.match(anchor["text"])
        if not match or absolute_url in seen_links:
            continue
        seen_links.add(absolute_url)
        results.append(
            {
                "title": match.group("title"),
                "link": absolute_url,
                "summary": "",
                "published": parse_date(match.group("date")),
            }
        )
    return results


def parse_anthropic_html(source: dict[str, Any], html_bytes: bytes) -> list[dict[str, Any]]:
    parser = AnchorParser()
    parser.feed(html_bytes.decode("utf-8", errors="ignore"))
    results: list[dict[str, Any]] = []
    seen_links: set[str] = set()
    pattern = re.compile(
        r"^(?P<date>[A-Z][a-z]{2} \d{1,2}, \d{4})\s+"
        r"(?P<category>Announcements|Product|Research)\s+"
        r"(?P<title>.+)$"
    )
    for anchor in parser.anchors:
        href = anchor["href"].strip()
        if not href:
            continue
        absolute_url = urllib.parse.urljoin(source["homepage"], href)
        if "/news/" not in absolute_url or absolute_url.rstrip("/") == source["homepage"].rstrip("/"):
            continue
        match = pattern.match(anchor["text"])
        if not match or absolute_url in seen_links:
            continue
        seen_links.add(absolute_url)
        results.append(
            {
                "title": match.group("title"),
                "link": absolute_url,
                "summary": "",
                "published": parse_date(match.group("date")),
            }
        )
    return results


def parse_google_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for item in items:
        haystack = f"{item['title']} {item['summary']}".lower()
        link = item["link"].lower()
        allowed_paths = (
            "/products/gemini/",
            "/products/gemini-app/",
            "/technology/ai/",
            "/innovation-and-ai/models-and-research/",
            "/innovation-and-ai/products/gemini-app/",
        )
        if not any(path in link for path in allowed_paths):
            continue
        if not any(term in haystack for term in ("gemini", "ai", "notebooklm", "deep research", "nano banana")):
            continue
        filtered.append(item)
    return filtered


def parse_openai_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for item in items:
        link = item["link"].lower()
        if "openai.com/academy/" in link:
            continue
        if not any(path in link for path in ("openai.com/index/", "openai.com/research/", "openai.com/news/")):
            continue
        filtered.append(item)
    return filtered


def get_source_items(source: dict[str, Any], cutoff: dt.datetime) -> list[dict[str, Any]]:
    last_error: Exception | None = None
    for feed in source["feeds"]:
        try:
            parsed = parse_feed(fetch_url(feed))
            if source["id"] == "openai":
                parsed = parse_openai_items(parsed)
            if source["id"] == "google":
                parsed = parse_google_items(parsed)
            recent = [item for item in parsed if item["published"] is None or item["published"] >= cutoff]
            recent.sort(key=lambda item: item["published"] or cutoff, reverse=True)
            deduped: list[dict[str, Any]] = []
            seen_links: set[str] = set()
            for item in recent:
                if item["link"] in seen_links:
                    continue
                deduped.append(item)
                seen_links.add(item["link"])
                if len(deduped) >= MAX_ITEMS_PER_SOURCE:
                    break
            if deduped:
                return deduped
        except Exception as exc:
            last_error = exc

    try:
        homepage_html = fetch_url(source["homepage"])
        if source["id"] == "openai":
            parsed = parse_openai_html(source, homepage_html)
        elif source["id"] == "anthropic":
            parsed = parse_anthropic_html(source, homepage_html)
        else:
            parsed = []
        recent = [item for item in parsed if item["published"] is None or item["published"] >= cutoff]
        recent.sort(key=lambda item: item["published"] or cutoff, reverse=True)
        if recent:
            return recent[:MAX_ITEMS_PER_SOURCE]
    except Exception as exc:
        last_error = exc

    if last_error:
        raise last_error
    return []


def format_date_fr(value: dt.datetime | None) -> str:
    if value is None:
        return "date inconnue"
    months = [
        "janv.",
        "fevr.",
        "mars",
        "avr.",
        "mai",
        "juin",
        "juil.",
        "aout",
        "sept.",
        "oct.",
        "nov.",
        "dec.",
    ]
    return f"{value.day} {months[value.month - 1]} {value.year}"


def build_newsletter(items_by_source: list[tuple[dict[str, Any], list[dict[str, Any]]]]) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    title = f"*AI.Watch Daily* | {format_date_fr(now)}"
    lines = [
        title,
        "",
        "Veille automatique des dernieres annonces IA publiees sur les sources officielles.",
        "",
    ]

    for source, items in items_by_source:
        lines.append(f"*{source['name']}*")
        if not items:
            lines.append(f"- Aucun nouvel article retenu. Source: {source['homepage']}")
            lines.append("")
            continue
        for item in items:
            summary = f" | {item['summary'][:160]}" if item["summary"] else ""
            lines.append(f"- *{format_date_fr(item['published'])}* | <{item['link']}|{item['title']}>{summary}")
        lines.append("")

    lines.extend(
        [
            "*Sources*",
            "- OpenAI: https://openai.com/news/company-announcements/",
            "- Anthropic: https://www.anthropic.com/news",
            "- Google AI: https://blog.google/technology/ai/",
        ]
    )
    return "\n".join(lines).strip()


def post_to_slack(webhook_url: str, text: str) -> None:
    payload = json.dumps({"text": text}).encode("utf-8")
    request = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        response_body = response.read().decode("utf-8", errors="replace").strip()
        if response.status >= 300:
            raise RuntimeError(f"Slack webhook returned HTTP {response.status}: {response_body}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate and send the AI.Watch newsletter to Slack.")
    parser.add_argument(
        "--lookback-hours",
        type=int,
        default=96,
        help="Only keep feed items newer than this many hours.",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print the generated newsletter to stdout.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not post to Slack, even if a webhook is configured.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=args.lookback_hours)

    items_by_source: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
    failures: list[str] = []
    for source in SOURCES:
        try:
            items = get_source_items(source, cutoff)
        except Exception as exc:
            failures.append(f"{source['name']}: {exc}")
            items = []
        items_by_source.append((source, items))

    if failures:
        for failure in failures:
            print(f"warning: {failure}", file=sys.stderr)

    if not any(items for _, items in items_by_source):
        print("No recent news items found across configured sources. Skipping Slack post.")
        return 0

    newsletter = build_newsletter(items_by_source)
    if args.stdout or args.dry_run:
        print(newsletter)

    webhook_url = os.getenv("SLACK_WEBHOOK_URL", "").strip()
    if args.dry_run:
        return 0

    if not webhook_url:
        print("SLACK_WEBHOOK_URL is not configured.", file=sys.stderr)
        return 2

    try:
        post_to_slack(webhook_url, newsletter)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"Failed to post to Slack: HTTP {exc.code} {body}", file=sys.stderr)
        return 3
    except Exception as exc:
        print(f"Failed to post to Slack: {exc}", file=sys.stderr)
        return 3

    print("Newsletter sent to Slack.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
