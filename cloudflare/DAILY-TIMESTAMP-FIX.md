# 2026-09-30 daily timestamp correction

Morning ZAR/MXN source snapshots reached Sakura but were rejected before GitHub publication: daily `2026-09-30` had incorrectly become `2026-09-30Z` (UTC midnight), later than the actual fetch on September 29 UTC.

Twelve Data documents that timezone=UTC only applies to intraday intervals; daily dates use exchange-local time. Forex's documented default is Australia/Sydney:
- https://twelvedata.com/news/april-2026-updates
- https://support.twelvedata.com/en/articles/5745849-timezones

The Worker now preserves datetime/source_date, reads exchange_timezone metadata (documented Forex fallback Australia/Sydney), and converts the local daily date midnight to an explicit UTC timestamp. timestamp_basis=exchange_date_midnight identifies this as a normalized date reference, not an exact quote or tick timestamp. Source timezone is preserved on daily candles. Analysis latest timestamp and age use that same normalized value. No quota, schedule, API path, indicator formula, or Sakura launcher change.

Supersedes older instructions to append Z or interpret a bare daily date as UTC midnight. Consumers should use the returned explicit datetime_utc and source timezone. Never rewrite old source fetch timestamps or upload expired snapshots as fresh.

Offline regression includes the reported pre-UTC-midnight case, Sydney DST boundaries, metadata override, unchanged intraday conversion, full seven-request analysis and actual Python mirror validation. Production verification is separate.
