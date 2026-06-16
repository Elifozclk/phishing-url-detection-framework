"""Collect first- and second-level internal links with Playwright."""
from __future__ import annotations

import argparse
import asyncio
import uuid
from pathlib import Path
from urllib.parse import urljoin, urlparse

import pandas as pd
from playwright.async_api import BrowserContext, async_playwright

STATIC_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico", ".pdf", ".zip", ".rar", ".7z", ".tar", ".gz", ".mp4", ".mp3", ".avi", ".mov", ".mkv", ".exe", ".msi", ".dmg")


def clean_link(base_url: str, href: str | None, allowed_domain: str):
    if not href or href.strip().startswith(("mailto:", "javascript:", "tel:", "#")):
        return None
    try:
        full = urljoin(base_url, href.strip())
        parsed = urlparse(full)
    except (TypeError, ValueError):
        return None
    if parsed.scheme not in {"http", "https"} or parsed.netloc != allowed_domain:
        return None
    path = parsed.path or "/"
    if path == "/" or path.lower().endswith(STATIC_EXTENSIONS):
        return None
    return full, path


async def extract_links(context: BrowserContext, url: str, domain: str, limit: int, timeout_ms: int):
    page = await context.new_page()
    links, seen = [], set()
    try:
        await page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
        for anchor in await page.query_selector_all("a"):
            cleaned = clean_link(url, await anchor.get_attribute("href"), domain)
            if not cleaned:
                continue
            full, path = cleaned
            if full in seen:
                continue
            seen.add(full)
            links.append((full, path))
            if len(links) >= limit:
                break
    except Exception:
        return []
    finally:
        await page.close()
    return links


async def crawl_row(row: dict, context: BrowserContext, semaphore: asyncio.Semaphore, first_limit: int, second_limit: int, timeout_ms: int):
    async with semaphore:
        main_url = row["main_url"]
        domain = urlparse(main_url).netloc
        if not domain:
            return []
        tree_id, results, visited = str(uuid.uuid4()), [], set()
        first = await extract_links(context, main_url, domain, first_limit, timeout_ms)
        for current, path in first:
            visited.add(current)
            results.append({"domain": row["domain"], "main_url": main_url, "parent_url": main_url, "current_url": current, "real_path": path, "depth": 1, "status": row.get("status"), "path_tree_id": tree_id})
        for parent, _ in first:
            for current, path in await extract_links(context, parent, domain, second_limit, timeout_ms):
                if current in visited:
                    continue
                visited.add(current)
                results.append({"domain": row["domain"], "main_url": main_url, "parent_url": parent, "current_url": current, "real_path": path, "depth": 2, "status": row.get("status"), "path_tree_id": tree_id})
        return results


async def run(args):
    frame = pd.read_csv(args.input).dropna(subset=["main_url"])
    semaphore = asyncio.Semaphore(args.concurrency)
    output = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0 (compatible; PhishingURLResearch/1.0)")
        tasks = [crawl_row(row, context, semaphore, args.first_level, args.second_level, args.timeout_ms) for row in frame.to_dict("records")]
        for completed in asyncio.as_completed(tasks):
            output.extend(await completed)
        await context.close()
        await browser.close()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(output).to_csv(args.output, index=False)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--first-level", type=int, default=5)
    parser.add_argument("--second-level", type=int, default=8)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--timeout-ms", type=int, default=10000)
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
