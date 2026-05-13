# Adding a New Rate-Limit Source

> Placeholder — fill in once the `sources/` interface is stabilised.

## Planned interface

Each source will implement a simple protocol:

```python
class RateLimitSource:
    def read(self) -> dict | None:
        """Return latest rate-limit data, or None if unavailable."""
        ...
```

## Steps to add a source

1. Create `busytag_meter/sources/<name>.py`
2. Implement `read()` returning a dict with at least:
   - `used_percentage: float`   (0–100)
   - `resets_at: str`           (ISO-8601 timestamp of the current rate-limit window)
   - `source: str`              (human label, e.g. `"claude_code"`)
3. Register in `busytag_meter/sources/__init__.py`
4. Add a test in `tests/test_sources.py`

## Deduplication rule

When merging updates from multiple sources (or multiple writer processes for the same source), apply the `resets_at`-first max rule documented in `docs/serial-survival-guide.md` — do **not** compare only `used_percentage`.
