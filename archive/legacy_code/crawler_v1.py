import asyncio
import os
import uuid
import random
from datetime import datetime
from urllib.parse import urlparse, urljoin

import pandas as pd
from playwright.async_api import async_playwright

# ====================== CONFIG ======================

input_path = "./domain_scan_results_part1_cleaned.csv"

output_path = "./real_paths_normal_playwright_final_3.csv"
no_url_output_path = "./no_urls_normal_playwright_final_3.csv"

# Derinlik ve link limitleri
MAX_FIRST_LEVEL_LINKS = 5
MAX_SECOND_LEVEL_LINKS = 8  # hız için 10'dan 5'e düşürdük

# Performans parametreleri
CONCURRENCY = 10            # hız için artırıldı
PAGE_TIMEOUT = 10000         # 5 saniye, çok yavaş siteleri erkenden bırak

# Checkpoint ayarı
CHECKPOINT_EVERY = 100      # her 100 main_url'de bir ara rapor

# Tüm dataset için TEST_LIMIT = None
TEST_LIMIT = None

STATIC_EXTENSIONS = (
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico",
    ".pdf", ".zip", ".rar", ".7z", ".tar", ".gz",
    ".mp4", ".mp3", ".avi", ".mov", ".mkv",
    ".exe", ".msi", ".dmg"
)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_3_1) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/16.4 Safari/605.1.15",
]


# ====================== HELPER ======================

def clean_link(base_url, href, allowed_domain):
    """Linki normalize eder, sadece aynı domaindeki, path içeren HTTP(S) linkleri döndürür.
       Hatalı IPv6 URL'ler TRY/EXCEPT ile tamamen yutuluyor."""
    if not href:
        return None

    href = href.strip()

    # mailto, javascript, tel, anchor vs. atla
    if href.startswith(("mailto:", "javascript:", "tel:", "#")):
        return None

    try:
        # Bazı bozuk IPv6 görünümlü URL'ler burada ValueError fırlatıyordu
        full = urljoin(base_url, href)
        parsed = urlparse(full)
    except ValueError:
        return None
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


# ====================== LINK EXTRACTION ======================

async def extract_links(context, base_url, domain, max_links):
    """Navigation-safe, crash-proof link extractor"""
    links = []
    seen = set()

    try:
        page = await context.new_page()
    except Exception:
        return []

    try:
        await page.goto(
            base_url,
            timeout=PAGE_TIMEOUT,
            wait_until="domcontentloaded"
        )
    except Exception:
        try:
            await page.close()
        except Exception:
            pass
        return []

    try:
        anchors = await page.query_selector_all("a")
    except Exception:
        try:
            await page.close()
        except Exception:
            pass
        return []

    for a in anchors:
        try:
            href = await a.get_attribute("href")
        except Exception:
            continue

        if not href:
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
    except Exception:
        pass

    return links


# ====================== CRAWL ONE ======================

async def crawl_one(row, context, semaphore, domain_id):
    domain = row["domain"]
    main_url = row["main_url"]
    status = row.get("status", None)

    parsed = urlparse(main_url)
    base_domain = parsed.netloc

    if not base_domain:
        return [], row

    async with semaphore:
        path_id = str(uuid.uuid4())
        visited = set()
        results = []

        try:
            # DEPTH 1
            depth1_links = await extract_links(
                context, main_url, base_domain, MAX_FIRST_LEVEL_LINKS
            )

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
                        "path_tree_id": path_id
                    })

            # DEPTH 2
            for full1, path1 in depth1_links:
                depth2_links = await extract_links(
                    context, full1, base_domain, MAX_SECOND_LEVEL_LINKS
                )

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
                            "path_tree_id": path_id
                        })

        except Exception:
            # Herhangi bir beklenmedik hata varsa bu domain'i "başarısız" say
            if not results:
                return [], row

        # Eğer hiç URL üretilmediyse failmeta olarak döndür
        return results, row if len(results) == 0 else None


# ====================== MAIN ======================

async def main():
    # ---- INPUT'u yükle ----
    df = pd.read_csv(input_path)
    if TEST_LIMIT is not None:
        df = df.head(TEST_LIMIT)

    # Aynı domainden birden fazla satır varsa istersen burayı açıp domain bazlı uniq yapabilirsin:
    # df = df.drop_duplicates(subset=["domain"])

    # ---- RESUME BİLGİSİ: daha önce işlenen domain'leri ve domain_id'yi oku ----
    processed_domains = set()
    total_written = 0
    total_fail = 0
    max_domain_id = 0

    if os.path.exists(output_path):
        try:
            df_out = pd.read_csv(output_path)
            if "domain" in df_out.columns:
                processed_domains.update(df_out["domain"].dropna().unique().tolist())
            if "domain_id" in df_out.columns:
                max_domain_id = int(df_out["domain_id"].max())
            total_written = len(df_out)
        except Exception:
            pass

    if os.path.exists(no_url_output_path):
        try:
            df_fail = pd.read_csv(no_url_output_path)
            if "domain" in df_fail.columns:
                processed_domains.update(df_fail["domain"].dropna().unique().tolist())
                # domain bazlı fail sayısı
                total_fail = len(set(df_fail["domain"].dropna().unique().tolist()))
        except Exception:
            pass

    # Şu ana kadar işlenmiş main_url sayısı = processed_domains'in uzunluğu
    processed = len(processed_domains)

    # Yeni domain_id başlangıcı
    domain_id_counter = max_domain_id + 1

    print("NORMAL CRAWLER MODU (RESUME + OPTIMIZED) BAŞLADI")
    print(f"Toplam main_url (input): {len(df)}")
    print(f"Daha önce işlenmiş domain sayısı : {processed}")
    print(f"Şu ana kadar yazılmış toplam URL : {total_written}")
    print(f"Şu ana kadar 'hiç URL üretmeyen' domain sayısı: {total_fail}")
    print("===============================================")

    buffer_results = []
    buffer_fail = []

    def flush():
        nonlocal buffer_results, buffer_fail, total_written, total_fail

        if buffer_results:
            df_out = pd.DataFrame(buffer_results)
            df_out.to_csv(
                output_path,
                mode="a",
                index=False,
                header=not os.path.exists(output_path)
            )
            total_written += len(df_out)
            buffer_results = []

        if buffer_fail:
            df_fail = pd.DataFrame(buffer_fail)
            df_fail.to_csv(
                no_url_output_path,
                mode="a",
                index=False,
                header=not os.path.exists(no_url_output_path)
            )
            # domain bazlı count tutmak için uniq domain say
            fail_domains = set(df_fail["domain"].dropna().unique().tolist())
            total_fail += len(fail_domains)
            buffer_fail = []

        print("\n========== ARA KAYIT ==========")
        print(f"Zaman: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"İşlenen main_url: {processed}")
        print(f"Toplam URL: {total_written}")
        print(f"Hiç URL üretmeyen: {total_fail}")
        print("================================\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        contexts = [
            await browser.new_context(
                user_agent=random.choice(USER_AGENTS),
                viewport={"width": 1280, "height": 900},
                locale="en-US"
            )
            for _ in range(CONCURRENCY)
        ]

        semaphore = asyncio.Semaphore(CONCURRENCY)
        rows = df.to_dict(orient="records")

        tasks = []

        # Her satır = bir main_url
        for i, row in enumerate(rows):
            domain = row["domain"]

            # RESUME: daha önce işlenen domain'leri atla
            if domain in processed_domains:
                continue

            ctx = contexts[len(tasks) % CONCURRENCY]

            domain_id = domain_id_counter
            domain_id_counter += 1

            tasks.append(asyncio.create_task(
                crawl_one(row, ctx, semaphore, domain_id)
            ))

        # Task'ler bittikçe işlenir
        for coro in asyncio.as_completed(tasks):
            results, failmeta = await coro
            processed += 1

            if results:
                buffer_results.extend(results)
            if failmeta:
                buffer_fail.append({
                    "domain": failmeta["domain"],
                    "main_url": failmeta["main_url"],
                    "status": failmeta.get("status", None)
                })

            if processed % CHECKPOINT_EVERY == 0:
                flush()

        # Son kalan buffer'ları da diske yaz
        flush()

        # Context'leri kapat
        for ctx in contexts:
            try:
                await ctx.close()
            except Exception:
                pass

        await browser.close()

    print("NORMAL CRAWLER (RESUME + OPTIMIZED) TAMAMLANDI")
    print(f"Toplam URL: {total_written}")
    print(f"Hiç URL üretmeyen domain sayısı: {total_fail}")


if __name__ == "__main__":
    asyncio.run(main())
