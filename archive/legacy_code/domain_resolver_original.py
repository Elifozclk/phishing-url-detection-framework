import pandas as pd
import requests
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import sys
import os

# -----------------------------
# AYARLAR
# -----------------------------
NUM_THREADS = 60
TIMEOUT = 4
CHECKPOINT_SAVE_EVERY = 5000
PROGRESS_PRINT_EVERY = 2000

requests.packages.urllib3.disable_warnings()

# -----------------------------
# DOSYA YOLLARI (part1)
# -----------------------------
MAIN_FILE = "Lutfen_son_domain_olsun_1_part2.csv"
OUTPUT_FILE = "domain_scan_results_part2.csv"


# -----------------------------
# DOMAIN LİSTESİNİ YÜKLE
# -----------------------------
if not os.path.exists(MAIN_FILE):
    print(f"HATA: {MAIN_FILE} bulunamadı!")
    sys.exit(1)

df = pd.read_csv(MAIN_FILE, header=None, names=["domain"])
df["domain"] = df["domain"].astype(str).strip()

df = df[df["domain"].str.lower() != "domain"].reset_index(drop=True)

if "main_url" not in df.columns:
    df["main_url"] = pd.NA
if "status" not in df.columns:
    df["status"] = pd.NA

mask = df["main_url"].isna()
domains_to_scan = df.loc[mask, "domain"].tolist()
total = len(domains_to_scan)

print(f"Taranacak domain sayısı (part1): {total}")

if total == 0:
    sys.exit(0)

# DNS test
def dns_exists(host):
    try:
        socket.getaddrinfo(host, 80)
        return True
    except:
        return False

SUBS = ["www", "www2", "portal", "app", "secure", "blog", "web", "panel", "login", "store", "cpanel", "mail"]

def normalize(root):
    r = root.lower().strip()
    if r.startswith("www."):
        r = r[4:]
    return r

def host_candidates(domain):
    root = normalize(domain)
    base = [root, f"www.{root}"]
    subs = [f"{s}.{root}" for s in SUBS]
    return base, subs

def build_urls(host):
    urls = []
    for sch in ["https", "http"]:
        for p in ["", "/", "/index.html"]:
            urls.append(f"{sch}://{host}{p}")
    return urls

HEAD = {
    "User-Agent":
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
}

def scan_single(domain):
    base, subs = host_candidates(domain)

    for host in base:
        if not dns_exists(host):
            continue
        for url in build_urls(host):
            try:
                r = requests.head(url, timeout=TIMEOUT, verify=False, allow_redirects=True, headers=HEAD)
                if r.status_code < 400:
                    g = requests.get(url, timeout=TIMEOUT, verify=False, allow_redirects=True, headers=HEAD)
                    if g.status_code < 400:
                        return domain, g.url, g.status_code
            except:
                pass
            try:
                g = requests.get(url, timeout=TIMEOUT, verify=False, allow_redirects=True, headers=HEAD)
                if g.status_code < 400:
                    return domain, g.url, g.status_code
            except:
                pass

    for host in subs:
        if not dns_exists(host):
            continue
        for url in build_urls(host):
            try:
                r = requests.head(url, timeout=TIMEOUT, verify=False, allow_redirects=True, headers=HEAD)
                if r.status_code < 400:
                    g = requests.get(url, timeout=TIMEOUT, verify=False, allow_redirects=True, headers=HEAD)
                    if g.status_code < 400:
                        return domain, g.url, g.status_code
            except:
                pass
            try:
                g = requests.get(url, timeout=TIMEOUT, verify=False, allow_redirects=True, headers=HEAD)
                if g.status_code < 400:
                    return domain, g.url, g.status_code
            except:
                pass

    return domain, None, None

processed = 0
start = time.time()

with ThreadPoolExecutor(max_workers=NUM_THREADS) as ex:
    futures = {ex.submit(scan_single, d): d for d in domains_to_scan}

    for f in as_completed(futures):
        domain, url, status = f.result()
        df.loc[df["domain"] == domain, ["main_url", "status"]] = [url, status]

        processed += 1

        if processed % PROGRESS_PRINT_EVERY == 0:
            print(f"Part1 -> {processed}/{total}")

        if processed % CHECKPOINT_SAVE_EVERY == 0:
            df.to_csv(OUTPUT_FILE, index=False)
            print("Ara kayıt (part1) alındı.")

df.to_csv(OUTPUT_FILE, index=False)
print("Part1 tamamlandı.")
