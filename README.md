# ig-proxy-tester

Collects free proxies from 40+ public sources and tests each one against the real Instagram API endpoint. Only proxies that actually work — no false positives from `robots.txt` checks.

## How it works

1. **Fetch** — downloads proxy lists from 40+ GitHub repos and public APIs in parallel (async HTTP)
2. **Test** — sends a real request to `i.instagram.com/api/v1/users/web_profile_info/` through each proxy
   - ✅ HTTP 200/404 → working
   - ❌ HTTP 429 → already rate-limited, rejected
   - ❌ timeout / error → dead, rejected
3. **Save** — writes working proxies to `proxies.txt`, shuffled

The test list is **randomised before testing**, so concurrent users get different results and don't all hammer the same proxies at the same time.

## Install

```bash
pip install httpx rich
```

## Usage

```bash
# Fetch all sources, test everything, save working proxies
python proxy_fetcher.py

# Re-test proxies already in proxies.txt
python proxy_fetcher.py --test-only

# Resume a previous run (skip already-tested proxies)
python proxy_fetcher.py --resume
```

## Output

```
Fetching proxies from all sources
Downloading 44 sources in parallel...
13 211 unique proxies collected

Testing against Instagram
120 parallel threads — 6s timeout per proxy — randomised order
⠸ ████████████░░░░░░░░░░░░░░░░░░  4 821/13 211  12 working  0:01:23

12 working proxies out of 13 211 tested
✓ 12 proxies saved to proxies.txt
```

## Why so few working proxies?

Free proxies from public GitHub lists are **datacenter IPs** — Instagram recognises and blocks entire subnets. Typical pass rates: 0.01–0.5%.

For reliable results, use **residential proxies** (e.g. [Webshare](https://webshare.io), [BrightData](https://brightdata.com)) and drop them in `proxies.txt` directly.

## Sources

Pulls from 44 sources across HTTP, HTTPS, SOCKS4, and SOCKS5:

| Category | Count |
|---|---|
| GitHub — HTTP | 23 |
| GitHub — SOCKS4 | 4 |
| GitHub — SOCKS5 | 7 |
| Public APIs | 10 |

Full list in [`proxy_fetcher.py`](proxy_fetcher.py) under `SOURCES`.

## Requirements

- Python 3.10+
- `httpx` — async-capable HTTP client
- `rich` — progress bar and terminal output

## Notes

- Threads are used for testing (not asyncio) because Windows' `ProactorEventLoop` has known issues with concurrent HTTPS-over-proxy connections
- Source fetching uses asyncio (`asyncio.gather`) since it's plain HTTPS with no proxy involved
- Each run overwrites `proxies.txt` unless `--resume` is used

## License

MIT
