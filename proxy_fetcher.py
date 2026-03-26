"""
Free Proxy Fetcher & Tester
============================
Collects proxies from 40+ public sources, tests them against a real
Instagram API endpoint, and saves only the working ones to proxies.txt.

The test list is shuffled before testing, so concurrent users get
different results — reducing overlap in the final working sets.

Usage:
  python proxy_fetcher.py             — fetch all sources, test, save
  python proxy_fetcher.py --test-only — re-test proxies already in proxies.txt
  python proxy_fetcher.py --resume    — skip proxies already tested in proxies.txt

Requirements:
  pip install httpx rich
"""

import sys
import re
import time
import asyncio
import random
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx
from rich.console import Console
from rich.progress import (
    Progress, BarColumn, TextColumn, TimeRemainingColumn,
    MofNCompleteColumn, SpinnerColumn,
)

console = Console()

PROXIES_FILE = Path(__file__).parent / "proxies.txt"

# Number of parallel threads for testing.
# Threads are used instead of asyncio because Windows' ProactorEventLoop
# does not reliably handle concurrent HTTPS-over-proxy (CONNECT tunneling).
MAX_WORKERS = 120

# ──────────────────────────────────────────────────────────────────────────────
# Proxy sources — 40+ public lists updated daily
# ──────────────────────────────────────────────────────────────────────────────

SOURCES = [
    # ── GitHub — HTTP ─────────────────────────────────────────────────────────
    ("github/TheSpeedX-http",       "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt"),
    ("github/ShiftyTR-http",        "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt"),
    ("github/monosans-http",        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt"),
    ("github/clarketm",             "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt"),
    ("github/jetkai-http",          "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-http.txt"),
    ("github/mertguvencli",         "https://raw.githubusercontent.com/mertguvencli/http-proxy-list/main/proxy-list/data.txt"),
    ("github/roosterkid",           "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt"),
    ("github/prxchk",               "https://raw.githubusercontent.com/prxchk/proxy-list/main/http.txt"),
    ("github/Anonym0usWork1221",     "https://raw.githubusercontent.com/Anonym0usWork1221/Free-Proxies/main/proxy_files/http_proxies.txt"),
    ("github/zloi-user",            "https://raw.githubusercontent.com/zloi-user/hideip.me/main/http.txt"),
    ("github/almroot",              "https://raw.githubusercontent.com/almroot/proxylist/master/list.txt"),
    ("github/sunny9577",            "https://raw.githubusercontent.com/sunny9577/proxy-scraper/master/proxies.txt"),
    ("github/rdavydov",             "https://raw.githubusercontent.com/rdavydov/proxy-list/main/proxies/http.txt"),
    ("github/HyperBeats",           "https://raw.githubusercontent.com/HyperBeats/proxy-list/main/http.txt"),
    ("github/B4RC0DE-TM",           "https://raw.githubusercontent.com/B4RC0DE-TM/proxy-list/main/HTTP.txt"),
    ("github/saschazesiger",        "https://raw.githubusercontent.com/saschazesiger/Free-Proxies/master/proxies/http.txt"),
    ("github/MuRongPIG",            "https://raw.githubusercontent.com/MuRongPIG/Proxy-Master/main/http.txt"),
    ("github/mmpx12",               "https://raw.githubusercontent.com/mmpx12/proxy-list/master/http.txt"),
    ("github/caliphdev",            "https://raw.githubusercontent.com/caliphdev/Proxy-List/master/http.txt"),
    ("github/rx443",                "https://raw.githubusercontent.com/rx443/proxy-list/online/http.txt"),
    ("github/vakhov",               "https://raw.githubusercontent.com/vakhov/fresh-proxy-list/master/http.txt"),
    ("github/fyvri",                "https://raw.githubusercontent.com/fyvri/fresh-proxy-list/main/sources/classic/http.txt"),
    ("github/hendrikbgr",           "https://raw.githubusercontent.com/hendrikbgr/Free-Proxy-Repo/master/proxy_list.txt"),
    # ── GitHub — SOCKS4 ───────────────────────────────────────────────────────
    ("github/TheSpeedX-socks4",     "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt"),
    ("github/ShiftyTR-socks4",      "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks4.txt"),
    ("github/monosans-socks4",      "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks4.txt"),
    ("github/Anonym0usWork1221-s4",  "https://raw.githubusercontent.com/Anonym0usWork1221/Free-Proxies/main/proxy_files/socks4_proxies.txt"),
    # ── GitHub — SOCKS5 ───────────────────────────────────────────────────────
    ("github/TheSpeedX-socks5",     "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt"),
    ("github/ShiftyTR-socks5",      "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks5.txt"),
    ("github/monosans-socks5",      "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt"),
    ("github/hookzof-socks5",       "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt"),
    ("github/jetkai-socks5",        "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-socks5.txt"),
    ("github/Anonym0usWork1221-s5",  "https://raw.githubusercontent.com/Anonym0usWork1221/Free-Proxies/main/proxy_files/socks5_proxies.txt"),
    ("github/B4RC0DE-TM-socks5",    "https://raw.githubusercontent.com/B4RC0DE-TM/proxy-list/main/SOCKS5.txt"),
    ("github/mmpx12-socks5",        "https://raw.githubusercontent.com/mmpx12/proxy-list/master/socks5.txt"),
    # ── Public APIs ───────────────────────────────────────────────────────────
    ("api/proxyscrape-http",        "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all"),
    ("api/proxyscrape-http-elite",  "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=5000&country=all&ssl=yes&anonymity=elite"),
    ("api/proxyscrape-socks4",      "https://api.proxyscrape.com/v2/?request=getproxies&protocol=socks4&timeout=10000&country=all"),
    ("api/proxyscrape-socks5",      "https://api.proxyscrape.com/v2/?request=getproxies&protocol=socks5&timeout=10000&country=all"),
    ("api/proxy-list-http",         "https://www.proxy-list.download/api/v1/get?type=http"),
    ("api/proxy-list-https",        "https://www.proxy-list.download/api/v1/get?type=https"),
    ("api/proxy-list-socks4",       "https://www.proxy-list.download/api/v1/get?type=socks4"),
    ("api/proxy-list-socks5",       "https://www.proxy-list.download/api/v1/get?type=socks5"),
    ("api/openproxy-space",         "https://openproxy.space/list/http"),
]

# ──────────────────────────────────────────────────────────────────────────────
# Parsing
# ──────────────────────────────────────────────────────────────────────────────

_PROXY_RE = re.compile(r"\b(\d{1,3}(?:\.\d{1,3}){3}:\d{2,5})\b")


def _parse_proxies(text: str, source_name: str) -> list[str]:
    """Extract host:port pairs and prefix with the correct protocol."""
    raw = _PROXY_RE.findall(text)
    if "socks5" in source_name:
        return [f"socks5://{p}" for p in raw]
    if "socks4" in source_name:
        return [f"socks4://{p}" for p in raw]
    return [f"http://{p}" for p in raw]


# ──────────────────────────────────────────────────────────────────────────────
# Source fetching — async (plain HTTPS downloads, no proxy involved)
# ──────────────────────────────────────────────────────────────────────────────

async def _fetch_source(session: httpx.AsyncClient, name: str, url: str) -> tuple[str, list[str]]:
    try:
        resp = await session.get(url, timeout=15)
        return name, _parse_proxies(resp.text, name)
    except Exception:
        return name, []


async def _fetch_all_async() -> list[str]:
    all_proxies: set[str] = set()
    console.print(f"[dim]Downloading {len(SOURCES)} sources in parallel...[/dim]")
    async with httpx.AsyncClient(follow_redirects=True) as session:
        results = await asyncio.gather(*[_fetch_source(session, n, u) for n, u in SOURCES])
    for _, proxies in results:
        all_proxies.update(proxies)
    return list(all_proxies)


def fetch_all_sources() -> list[str]:
    return asyncio.run(_fetch_all_async())


# ──────────────────────────────────────────────────────────────────────────────
# Proxy testing — thread-based
#
# Threads are more reliable than asyncio on Windows for concurrent HTTPS
# connections through proxies (the ProactorEventLoop has known issues with
# CONNECT tunneling). Each proxy is tested against the real Instagram API
# endpoint used by the scraper — not just robots.txt.
# ──────────────────────────────────────────────────────────────────────────────

# Real API endpoint used by the scraper.
# HTTP 200/404 → proxy works.  HTTP 429 → proxy is already rate-limited (rejected).
# Timeout / connection error → proxy is dead (rejected).
_TEST_URL     = "https://i.instagram.com/api/v1/users/web_profile_info/?username=instagram"
_TEST_TIMEOUT = 6

_TEST_HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "X-IG-App-ID":     "936619743392459",
    "X-ASBD-ID":       "198387",
    "X-IG-WWW-Claim":  "0",
}

_file_lock = threading.Lock()


def _test_proxy(proxy: str) -> tuple[str, bool]:
    try:
        with httpx.Client(
            proxy=proxy,
            timeout=_TEST_TIMEOUT,
            headers=_TEST_HEADERS,
            follow_redirects=True,
        ) as client:
            resp = client.get(_TEST_URL)
            return proxy, resp.status_code in (200, 404)
    except Exception:
        return proxy, False


def test_proxies(proxies: list[str]) -> list[str]:
    """
    Test proxies in parallel using a thread pool.
    The list is shuffled before testing so that concurrent users
    process proxies in a different order and get varied results.
    """
    working: list[str] = []
    candidates = proxies.copy()
    random.shuffle(candidates)  # randomise order before testing

    PROXIES_FILE.write_text("")

    with Progress(
        SpinnerColumn(),
        BarColumn(bar_width=36),
        MofNCompleteColumn(),
        TextColumn("[green]{task.fields[found]} working[/green]"),
        TimeRemainingColumn(),
        console=console,
        refresh_per_second=8,
    ) as progress:
        task = progress.add_task("Testing proxies...", total=len(candidates), found=0)

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(_test_proxy, p): p for p in candidates}

            for future in as_completed(futures):
                proxy, ok = future.result()

                if ok:
                    working.append(proxy)
                    with _file_lock:
                        with open(PROXIES_FILE, "a") as f:
                            f.write(proxy + "\n")

                progress.advance(task)
                progress.update(task, found=len(working))

    return working


# ──────────────────────────────────────────────────────────────────────────────
# Save / load helpers
# ──────────────────────────────────────────────────────────────────────────────

def save_proxies(proxies: list[str]) -> None:
    """Shuffle and overwrite proxies.txt with the final working set."""
    if not proxies:
        return
    shuffled = proxies.copy()
    random.shuffle(shuffled)
    PROXIES_FILE.write_text("\n".join(shuffled) + "\n")
    console.print(f"[green]✓ {len(proxies)} proxies saved to {PROXIES_FILE.name}[/green]")


def load_existing() -> list[str]:
    if not PROXIES_FILE.exists():
        return []
    return [l.strip() for l in PROXIES_FILE.read_text().splitlines()
            if l.strip() and not l.startswith("#")]


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────

def run(test_only: bool = False, fresh: bool = False) -> None:
    """
    Default behaviour (no flags):
      1. Re-validate existing proxies in proxies.txt — keep the ones still working.
      2. Fetch new proxies from all sources, skip any already known.
      3. Test new candidates and merge with survivors from step 1.

    --test-only : only re-validate existing proxies, skip fetching new ones.
    --fresh     : ignore existing proxies entirely, start from scratch.
    """
    survivors: list[str] = []

    # ── Step 1: re-validate existing proxies ──────────────────────────────────
    existing = load_existing()
    if existing and not fresh:
        console.rule("[bold]Re-validating existing proxies[/bold]")
        console.print(f"[dim]Checking {len(existing)} proxies already in proxies.txt...[/dim]")
        survivors = test_proxies(existing)
        console.print(
            f"[cyan]{len(survivors)}/{len(existing)} existing proxies still working[/cyan]"
        )
    elif fresh:
        console.print("[dim]--fresh: ignoring existing proxies.txt[/dim]")

    if test_only:
        if not existing:
            console.print("[yellow]No proxies found in proxies.txt[/yellow]")
            return
        _finish(survivors, len(existing))
        return

    # ── Step 2: fetch new proxies from all sources ────────────────────────────
    console.rule("[bold]Fetching proxies from all sources[/bold]")
    all_fetched = fetch_all_sources()
    known = set(existing)
    new_candidates = [p for p in all_fetched if p not in known]
    console.print(
        f"[cyan]{len(all_fetched)} unique proxies collected — "
        f"{len(new_candidates)} new (not in proxies.txt)[/cyan]"
    )

    if not new_candidates:
        console.print("[yellow]No new proxies to test.[/yellow]")
        _finish(survivors, 0)
        return

    # ── Step 3: test new candidates ───────────────────────────────────────────
    console.rule("[bold]Testing new proxies against Instagram[/bold]")
    console.print(f"[dim]{MAX_WORKERS} parallel threads — {_TEST_TIMEOUT}s timeout — randomised order[/dim]")
    new_working = test_proxies(new_candidates)
    console.print(
        f"[cyan]{len(new_working)} new working proxies[/cyan] out of {len(new_candidates)} tested"
    )

    _finish(survivors + new_working, len(new_candidates))


def _finish(working: list[str], tested: int) -> None:
    """Print summary and save."""
    console.print(f"\n[bold green]{len(working)} working proxies total[/bold green]")
    if working:
        save_proxies(working)
        sample = random.sample(working, min(5, len(working)))
        console.print("\nSample:")
        for p in sample:
            console.print(f"  [dim]{p}[/dim]")
    else:
        console.print("[yellow]No working proxies found.[/yellow]")
        console.print("[dim]Tip: free datacenter proxies are often blocked. Consider residential proxies (Webshare, BrightData).[/dim]")


if __name__ == "__main__":
    test_only = "--test-only" in sys.argv
    fresh     = "--fresh"     in sys.argv
    run(test_only=test_only, fresh=fresh)
