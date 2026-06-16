import asyncio
import os
import uuid
import random
from datetime import datetime
from urllib.parse import urlparse, urljoin

import pandas as pd
from playwright.async_api import async_playwright

# ======================================================
# CONFIG
# ======================================================

input_path = "./domain_scan_results_part1_cleaned.csv"

output_path = "./real_paths_normal_playwright_final_3.csv"
no_url_output_path = "./no_urls_normal_playwright_final_3.csv"

# Depth ayarları
MAX_FIRST_LEVEL_LINKS = 5
MAX_SECOND_LEVEL_LINKS = 8

# Performans
CONCURRENCY = 10
PAGE_TIMEOUT = 10000    # 10 saniye timeout

# Ara kayıt
CHECKPOINT_EVERY = 100

# Context reset
RESET_CONTEXT_EVERY = 200

# Test limit (None = tüm dataset)
TEST_LIMIT = None

STATIC_EXTENSIONS = (
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico",
    ".pdf", ".zip", ".rar", ".7z", ".tar", ".gz",
    ".mp4", ".mp3", ".avi", ".mov", ".mkv",
    ".exe", ".msi", ".dmg"
)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Safari/605.1.15"
]


# ======================================================
# HELPER
# ======================================================

def clean_link(base_url, href, allowed_domain):
    if not href:
        return None

    href = href.strip()

    if href.startswith(("mailto:", "javascript:", "tel:", "#")):
        return None

    try:
        full = urljoin(base_url, href)
        parsed = urlparse(full)
    except Exception:
        return None

    if parsed.scheme not in ("http", "https"):
        return None

    if parsed.netloc != allowed_domain:
        return None

    path = parsed.path or "/"
    if path in ("", "/"):
        return None

    for ext in STATIC_EXTENSIONS:
        if path.lower().endswith(ext):
            return None

    return full, path


# ======================================================
# LINK EXTRACTION
# ======================================================

async def extract_links(context, base_url, domain, max_links):
    links = []
    seen = set()

    try:
        page = await context.new_page()
    except Exception:
        return []

    try:
        await page.goto(base_url, timeout=PAGE_TIMEOUT, wait_until="domcontentloaded")
    except Exception:
        try:
            await page.close()
        except:
            pass
        return []

    try:
        anchors = await page.query_selector_all("a")
    except Exception:
        try:
            await page.close()
        except:
            pass
        return []

    for a in anchors:
        try:
            href = await a.get_attribute("href")
        except:
            continue

        cleaned = clean_link(base_url, href, domain)
        if not cleaned:
            continue

        full, path = cleaned
        if path in seen:
            continue

        seen.add(path)
        links.append((full, path))

        if len(links) >= max_links:
            break

    try:
        await page.close()
    except:
        pass

    return links


# ======================================================
# CRAWL ONE
# ======================================================

async def crawl_one(row, context, semaphore, domain_id):
    domain = row["domain"]
    main_url = row["main_url"]
    status = row.get("status", None)

    parsed = urlparse(main_url)
    base_domain = parsed.netloc

    if not base_domain:
        return [], row

    async with semaphore:
        path_tree_id = str(uuid.uuid4())
        visited = set()
        results = []

        try:
            # DEPTH 1
            depth1_links = await extract_links(context, main_url, base_domain, MAX_FIRST_LEVEL_LINKS)

            for full, path in depth1_links:
                if full not in visited:
                    visited.add(full)
                    results.append({
                        "domain_id": domain_id,
                        "domain": domain,
                        "main_url": main_url,
                        "parent_url": main_url,
                        "current_url": full,
                        "real_path": path,
                        "depth": 1,
                        "status": status,
                        "path_tree_id": path_tree_id
                    })

            # DEPTH 2
            for full1, path1 in depth1_links:
                depth2_links = await extract_links(context, full1, base_domain, MAX_SECOND_LEVEL_LINKS)
                for full2, path2 in depth2_links:
                    if full2 not in visited:
                        visited.add(full2)
                        results.append({
                            "domain_id": domain_id,
                            "domain": domain,
                            "main_url": main_url,
                            "parent_url": full1,
                            "current_url": full2,
                            "real_path": path2,
                            "depth": 2,
                            "status": status,
                            "path_tree_id": path_tree_id
                        })

        except Exception:
            if not results:
                return [], row

        return results, None if results else row


# ======================================================
# CONTEXT RESETTER
# ======================================================

async def reset_contexts(browser, old_contexts):
    for ctx in old_contexts:
        try:
            await ctx.close()
        except:
            pass

    new_contexts = [
        await browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport={"width": 1280, "height": 900},
            locale="en-US"
        ) for _ in range(CONCURRENCY)
    ]

    print("\n[+] CONTEXT RESETLENDİ (RAM Temizlendi)\n")
    return new_contexts


# ======================================================
# MAIN
# ======================================================

async def main():
    df = pd.read_csv(input_path)
    if TEST_LIMIT is not None:
        df = df.head(TEST_LIMIT)

    processed_domains = set()
    total_written = 0
    total_fail = 0
    max_domain_id = 0

    if os.path.exists(output_path):
        try:
            df2 = pd.read_csv(output_path)
            processed_domains.update(df2["domain"].dropna().unique().tolist())
            max_domain_id = int(df2["domain_id"].max())
            total_written = len(df2)
        except:
            pass

    if os.path.exists(no_url_output_path):
        try:
            df3 = pd.read_csv(no_url_output_path)
            processed_domains.update(df3["domain"].dropna().unique().tolist())
            total_fail = len(set(df3["domain"].dropna().unique().tolist()))
        except:
            pass

    processed = len(processed_domains)
    domain_id_counter = max_domain_id + 1

    print("=== NORMAL CRAWLER BAŞLADI ===")
    print(f"Toplam main_url: {len(df)}")
    print(f"Daha önce işlenen domain: {processed}")
    print("=================================\n")

    buffer_results = []
    buffer_fail = []

    def flush():
        nonlocal buffer_results, buffer_fail, total_written, total_fail

        if buffer_results:
            pd.DataFrame(buffer_results).to_csv(
                output_path, mode="a", index=False,
                header=not os.path.exists(output_path)
            )
            total_written += len(buffer_results)
            buffer_results = []

        if buffer_fail:
            pd.DataFrame(buffer_fail).to_csv(
                no_url_output_path, mode="a", index=False,
                header=not os.path.exists(no_url_output_path)
            )
            total_fail += len(buffer_fail)
            buffer_fail = []

        print("\n--- ARA KAYIT ---")
        print(f"İşlenen main_url: {processed}")
        print(f"Toplam URL: {total_written}")
        print(f"Hiç URL üretmeyen: {total_fail}")
        print("------------------\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        contexts = [
            await browser.new_context(
                user_agent=random.choice(USER_AGENTS),
                viewport={"width": 1280, "height": 900},
                locale="en-US"
            ) for _ in range(CONCURRENCY)
        ]

        semaphore = asyncio.Semaphore(CONCURRENCY)
        rows = df.to_dict(orient="records")
        tasks = []

        for row in rows:
            domain = row["domain"]
            if domain in processed_domains:
                continue

            ctx = contexts[len(tasks) % CONCURRENCY]
            tasks.append(asyncio.create_task(
                crawl_one(row, ctx, semaphore, domain_id_counter)
            ))
            domain_id_counter += 1

        # Completed tasks
        for coro in asyncio.as_completed(tasks):
            results, failed = await coro
            processed += 1

            if results:
                buffer_results.extend(results)
            if failed:
                buffer_fail.append({
                    "domain": failed["domain"],
                    "main_url": failed["main_url"],
                    "status": failed.get("status", None)
                })

            if processed % CHECKPOINT_EVERY == 0:
                flush()

            # ==== CONTEXT RESET ====
            if processed % RESET_CONTEXT_EVERY == 0:
                contexts = await reset_contexts(browser, contexts)

        flush()

        for ctx in contexts:
            try:
                await ctx.close()
            except:
                pass

        await browser.close()

    print("\n=== TARAYICI TAMAMLANDI ===")
    print(f"Toplam URL: {total_written}")
    print(f"Başarısız domain sayısı: {total_fail}")


if __name__ == "__main__":
    asyncio.run(main())
