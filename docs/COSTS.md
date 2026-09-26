# Tifo data pipeline: monthly AWS cost

- **Region:** ap-south-1 (Mumbai), the same region as cinema and cards.
- **Prices:** from the AWS Pricing API on 2026-09-26.
- **Runtime:** from the deployed functions' CloudWatch `REPORT` lines on 2026-09-26.

## Prices used

| item | price |
|---|---|
| Lambda arm64 compute | $0.0000133334 per GB-s (first 7.5 bn GB-s) |
| Lambda requests | $0.20 per million |
| S3 Standard storage | $0.025 per GB-month |
| S3 PUT/COPY/POST/LIST | $0.005 per 1,000 |
| S3 GET | $0.0004 per 1,000 |
| CloudFront, Middle East, data out | $0.110 per GB (first 10 TB) |
| CloudFront, Middle East, HTTPS requests | $0.012 per 10,000 |
| CloudWatch Logs ingestion | $0.67 per GB (storage $0.03 per GB-month, 14-day retention) |
| EventBridge scheduled rules | free |

S3 to CloudFront transfer is free, and so is Lambda to S3 in the same region.

## Measured behaviour

| function | memory | invocations/month | billed duration |
|---|---|---|---|
| `elyoxe-football-poller`, live minute (3 passes at 0/20/40 s) | 256 MB | ≈15,800 | 41–43 s (sleeps between passes are billed) |
| `elyoxe-football-poller`, idle minute | 256 MB | ≈27,400 | 2–3 s steady; 6.3 s on average in the first hours while the ledger backfill runs |
| `elyoxe-football-analytics` (every 10 min) | 512 MB | 4,320 | first runs 85–115 s (history backfill), then 7–30 s (26.7 s average over the first hour) |

- **Measured hour:** 2026-09-26 19:45–20:45 UTC, with the ledger backfill still running. The poller made 62 runs (12 live at 22.8 files written each, 50 idle at 20.9) and wrote 1,320 public files. The analytics function made 4 runs and wrote 376 files. State writes add ≈3 per poller run (`poller.json`, `hashes.json`, ledgers).
- **Live minutes:** 15,800 is the union of [kickoff − 75 min, kickoff + 150 min] over the 426 tracked matches FotMob lists in the next 30 days. That covers 32 competitions, including five big European leagues, the UEFA club competitions, the Saudi and Qatar leagues and the AFC, and works out to about 37% of all minutes. Removing the European competitions from `competitions.yaml` would roughly halve it.
- **Peak memory:** poller 145–174 MB, analytics 194 MB. The HTTP cache now evicts expired bodies, so warm containers stop growing.
- **Unchanged content:** it is not re-uploaded, because the hash ignores the `generated` stamp. After the backfill, idle runs write mostly `health.json`, the day files and the files whose content changed.

## Monthly estimate, without users

| item | calculation | $/month |
|---|---|---|
| Poller, live minutes | 15,800 × 42.5 s × 0.25 GB = 167,900 GB-s | 2.24 |
| Poller, idle minutes | 27,400 × 4 s × 0.25 GB = 27,400 GB-s | 0.37 |
| Analytics | 4,320 × 15 s × 0.5 GB = 32,400 GB-s | 0.43 |
| Lambda requests | 47,520 × $0.20/M | 0.01 |
| S3 PUTs | measured 1,700/hour during backfill (≈1.2 M/month); steady state ≈ 15/run → ≈ 0.8 M/month | 4.00–6.20 |
| S3 GETs | ≈ 15 per poller run + analytics reads ≈ 0.75 M/month | 0.30 |
| S3 storage | < 1 GB (≈ 5–10k small objects) | 0.03 |
| CloudWatch Logs | ≈ 60 MB | 0.04 |
| **Total** | | **≈ $7.5–9.7** |

- **Lambda free tier:** 400,000 GB-s and 1 M requests per month, always free. It is **shared by the whole account** (cards, wa-agent, contact-form, mailbox and others). If those leave it unused, the Lambda lines (≈ $3.0) drop to $0 and the total is ≈ $4.5–6.7.
- **S3 PUTs are the largest line.** The cheapest lever is to drop `live_pass_seconds` from three passes to two (−⅓ of live writes and compute).

## CloudFront, with users

- **Always-free tier:** 1 TB of data transfer out and 10 M HTTPS requests per month.
- **Object sizes, gzip:** `live.json` and day files are 2–10 KB, and a match file is 10–40 KB.
- **Estimate:** each assumes 40 requests of about 10 KB per visit, plus live polling at 20 s on match days.

| monthly visits | requests | data | CloudFront cost |
|---|---|---|---|
| 30,000 | ≈1.5 M | ≈15 GB | $0 (free tier) |
| 300,000 | ≈15 M | ≈150 GB | ≈ $6 (5 M requests over the free tier) |
| 3,000,000 | ≈150 M | ≈1.5 TB | ≈ $168 requests + ≈ $56 data |

- **Requests drive the cost, not bytes.** A page that polls `live.json` every 10 s would double the live-day requests; every 20 s matches the poller.

## Upgrade paths (priced)

- **API-Football (paid source):** swap `sources/apifootball.py` in when FotMob stops working. The plan prices were not verified, because the pricing page is JavaScript-rendered and needs a signup.
- **TheSportsDB premium:** $9/month (verified on its docs page on 2026-09-26). It removes the 5-row caps, so it works as a second fallback for tables.
- **Custom domain (`tifo.elyoxe.com`):** a free ACM certificate plus one Route53 record in the existing zone. Route53 queries cost $0.40 per million.
