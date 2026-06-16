"""Resolve domain names to reachable HTTP(S) URLs.

Example:
    python -m src.data.resolve_domains --input data/raw/domains.csv \
        --output data/interim/domain_scan_results.csv
"""
from __future__ import annotations

import argparse
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

SUBDOMAINS = ("www", "www2", "portal", "app", "secure", "blog", "web", "panel", "login", "store", "cpanel", "mail")
USER_AGENT = "Mozilla/5.0 (compatible; PhishingURLResearch/1.0)"


def normalize_domain(value: str) -> str:
    domain = str(value).strip().lower()
    for prefix in ("https://", "http://"):
        if domain.startswith(prefix):
            domain = domain[len(prefix):]
    domain = domain.split("/", 1)[0]
    return domain[4:] if domain.startswith("www.") else domain


def dns_exists(host: str) -> bool:
    try:
        socket.getaddrinfo(host, 80)
        return True
    except OSError:
        return False


def candidate_hosts(domain: str) -> list[str]:
    root = normalize_domain(domain)
    return [root, f"www.{root}", *[f"{sub}.{root}" for sub in SUBDOMAINS]]


def resolve_one(domain: str, timeout: float = 4.0) -> tuple[str, Optional[str], Optional[int]]:
    headers = {"User-Agent": USER_AGENT}
    for host in candidate_hosts(domain):
        if not dns_exists(host):
            continue
        for scheme in ("https", "http"):
            for suffix in ("", "/", "/index.html"):
                url = f"{scheme}://{host}{suffix}"
                try:
                    response = requests.get(url, timeout=timeout, verify=True, allow_redirects=True, headers=headers)
                    if response.status_code < 400:
                        return domain, response.url, response.status_code
                except requests.RequestException:
                    continue
    return domain, None, None


def run(input_path: Path, output_path: Path, threads: int, timeout: float, checkpoint_every: int) -> None:
    frame = pd.read_csv(input_path)
    if "domain" not in frame.columns:
        frame = frame.rename(columns={frame.columns[0]: "domain"})
    frame["domain"] = frame["domain"].astype(str).map(normalize_domain)
    frame = frame.drop_duplicates("domain").reset_index(drop=True)
    frame["main_url"] = pd.NA
    frame["status"] = pd.NA

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=threads) as executor:
        futures = {executor.submit(resolve_one, domain, timeout): domain for domain in frame["domain"]}
        for index, future in enumerate(as_completed(futures), start=1):
            domain, url, status = future.result()
            frame.loc[frame["domain"].eq(domain), ["main_url", "status"]] = [url, status]
            if checkpoint_every and index % checkpoint_every == 0:
                frame.to_csv(output_path, index=False)
                print(f"Processed {index}/{len(frame)} domains")
    frame.to_csv(output_path, index=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--threads", type=int, default=30)
    parser.add_argument("--timeout", type=float, default=4.0)
    parser.add_argument("--checkpoint-every", type=int, default=500)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(args.input, args.output, args.threads, args.timeout, args.checkpoint_every)
