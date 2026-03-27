#!/usr/bin/env python3
"""基于 Crossref 的外文参考文献轻量核验脚本。

用途：
1. 用 DOI 或标题查询 Crossref；
2. 核对标题、作者、年份、DOI、期刊/会议名称；
3. 输出适合人工复核的可读结果。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Iterable


USER_AGENT = "EssayReferenceVerifier/1.0 (local academic workflow)"


@dataclass
class FieldCheck:
    name: str
    expected: str
    actual: str
    status: str


def normalize_text(value: str) -> str:
    value = value or ""
    value = value.lower()
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", value)
    return value.strip()


def fetch_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def crossref_title(item: dict[str, Any]) -> str:
    titles = item.get("title") or []
    return titles[0] if titles else ""


def crossref_authors(item: dict[str, Any]) -> list[str]:
    authors = []
    for author in item.get("author", []):
        given = (author.get("given") or "").strip()
        family = (author.get("family") or "").strip()
        full = " ".join(part for part in (given, family) if part).strip()
        if full:
            authors.append(full)
    return authors


def crossref_year(item: dict[str, Any]) -> str:
    for key in ("issued", "published-print", "published-online", "published", "created"):
        node = item.get(key) or {}
        parts = node.get("date-parts") or []
        if parts and parts[0]:
            return str(parts[0][0])
    return ""


def crossref_container(item: dict[str, Any]) -> str:
    containers = item.get("container-title") or []
    if containers:
        return containers[0]
    publisher = item.get("publisher") or ""
    return str(publisher)


def safe_string(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def compare_title(expected: str, actual: str) -> FieldCheck:
    if not expected:
        return FieldCheck("标题", "", actual, "未提供")
    exp = normalize_text(expected)
    act = normalize_text(actual)
    status = "匹配" if exp == act else "不匹配"
    return FieldCheck("标题", expected, actual, status)


def compare_doi(expected: str, actual: str) -> FieldCheck:
    if not expected:
        return FieldCheck("DOI", "", actual, "未提供")
    exp = normalize_text(expected)
    act = normalize_text(actual)
    status = "匹配" if exp == act else "不匹配"
    return FieldCheck("DOI", expected, actual, status)


def compare_year(expected: str, actual: str) -> FieldCheck:
    if not expected:
        return FieldCheck("年份", "", actual, "未提供")
    status = "匹配" if safe_string(expected) == safe_string(actual) else "不匹配"
    return FieldCheck("年份", expected, actual, status)


def compare_author(expected: str, authors: Iterable[str]) -> FieldCheck:
    actual = "; ".join(authors)
    if not expected:
        return FieldCheck("作者", "", actual, "未提供")

    exp = normalize_text(expected)
    candidates = [normalize_text(author) for author in authors]
    status = "不匹配"
    for author in candidates:
        if exp and (exp in author or author in exp):
            status = "匹配"
            break
    return FieldCheck("作者", expected, actual, status)


def compare_venue(expected: str, actual: str) -> FieldCheck:
    if not expected:
        return FieldCheck("期刊/会议", "", actual, "未提供")
    exp = normalize_text(expected)
    act = normalize_text(actual)
    status = "匹配" if exp and (exp in act or act in exp) else "不匹配"
    return FieldCheck("期刊/会议", expected, actual, status)


def choose_best_match(items: list[dict[str, Any]], args: argparse.Namespace) -> dict[str, Any] | None:
    if not items:
        return None

    def score(item: dict[str, Any]) -> int:
        total = 0
        title = crossref_title(item)
        authors = crossref_authors(item)
        year = crossref_year(item)
        venue = crossref_container(item)

        if args.title and normalize_text(args.title) == normalize_text(title):
            total += 8
        if args.author and compare_author(args.author, authors).status == "匹配":
            total += 4
        if args.year and compare_year(args.year, year).status == "匹配":
            total += 3
        if args.venue and compare_venue(args.venue, venue).status == "匹配":
            total += 2
        total += int(float(item.get("score") or 0))
        return total

    return max(items, key=score)


def fetch_work(args: argparse.Namespace) -> dict[str, Any]:
    if args.doi:
        doi = urllib.parse.quote(args.doi, safe="")
        payload = fetch_json(f"https://api.crossref.org/works/{doi}")
        return payload["message"]

    query = urllib.parse.quote(args.title)
    payload = fetch_json(f"https://api.crossref.org/works?query.title={query}&rows=5")
    item = choose_best_match(payload["message"].get("items", []), args)
    if not item:
        raise LookupError("Crossref 未返回可用结果")
    return item


def summarize(checks: list[FieldCheck]) -> str:
    mismatches = [check for check in checks if check.status == "不匹配"]
    matches = [check for check in checks if check.status == "匹配"]
    if mismatches:
        return "存在不匹配，需人工复核"
    if matches:
        return "基本匹配，可作为后续人工复核基础"
    return "信息不足，需人工复核"


def main() -> int:
    parser = argparse.ArgumentParser(description="核验外文参考文献的基础元数据")
    parser.add_argument("--doi", help="待核验 DOI")
    parser.add_argument("--title", help="待核验标题")
    parser.add_argument("--author", help="待核验作者，可写姓或全名")
    parser.add_argument("--year", help="待核验年份")
    parser.add_argument("--venue", help="待核验期刊或会议名称")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    if not args.doi and not args.title:
        parser.error("至少需要提供 --doi 或 --title")

    try:
        item = fetch_work(args)
    except urllib.error.HTTPError as exc:
        print(f"Crossref 请求失败：HTTP {exc.code}", file=sys.stderr)
        return 2
    except urllib.error.URLError as exc:
        print(f"网络请求失败：{exc.reason}", file=sys.stderr)
        return 2
    except LookupError as exc:
        print(str(exc), file=sys.stderr)
        return 3

    actual_title = crossref_title(item)
    actual_authors = crossref_authors(item)
    actual_year = crossref_year(item)
    actual_doi = safe_string(item.get("DOI"))
    actual_venue = crossref_container(item)

    checks = [
        compare_title(args.title or "", actual_title),
        compare_author(args.author or "", actual_authors),
        compare_year(args.year or "", actual_year),
        compare_doi(args.doi or "", actual_doi),
        compare_venue(args.venue or "", actual_venue),
    ]

    result = {
        "query_mode": "doi" if args.doi else "title",
        "crossref": {
            "title": actual_title,
            "authors": actual_authors,
            "year": actual_year,
            "doi": actual_doi,
            "venue": actual_venue,
            "url": safe_string(item.get("URL")),
            "type": safe_string(item.get("type")),
        },
        "checks": [check.__dict__ for check in checks],
        "summary": summarize(checks),
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print(f"校验结论：{result['summary']}")
    print(f"查询方式：{result['query_mode']}")
    print("Crossref 命中：")
    print(f"- 标题：{actual_title}")
    print(f"- 作者：{'; '.join(actual_authors)}")
    print(f"- 年份：{actual_year}")
    print(f"- DOI：{actual_doi}")
    print(f"- 期刊/会议：{actual_venue}")
    print(f"- 类型：{safe_string(item.get('type'))}")
    print("字段核对：")
    for check in checks:
        print(f"- {check.name}：{check.status} | 期望={check.expected or '未提供'} | 实际={check.actual or '空'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
