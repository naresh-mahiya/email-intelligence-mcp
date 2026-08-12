# InboxValid MCP Prototype

A lightweight, MCP-compatible **email intelligence** server inspired by InboxValid's real-time
verification workflow. It exposes three discoverable tools that an AI agent or LLM client can call
as structured functions:

| Tool | Layer | Purpose |
|------|-------|---------|
| `verify_email` | Validation | Real-time single-address verification (syntax, disposable, MX). |
| `clean_email_list` | Hygiene | Bulk dedupe + verification with summary statistics. |
| `assess_signup_risk` | Intelligence | Onboarding / fraud decision built on the verification signals. |

All three share a **single validation engine** (`verify_email`) — the hygiene and risk tools reuse it
rather than re-implementing checks.

```
                verify_email()          <- core validation engine
                     ^  ^
         ┌───────────┘  └───────────┐
 clean_email_list()          assess_signup_risk()
```

---

## Features

- Email **syntax** validation (normalize + regex)
- **Disposable / throwaway** domain detection
- **Real DNS MX** lookup via `dnspython` (with timeout + graceful failure)
- Structured, risk-oriented responses (`status`, `reason`, `risk_score`, `checks`)
- **MCP tool exposure** so agents can discover and invoke verification as a typed tool
- Single-email verification — `verify_email`
- Bulk list cleaning + dedupe — `clean_email_list`
- Signup risk scoring + decision — `assess_signup_risk`

---

## Project layout

```
tvaram_mcp/
├── server.py              # MCP server; registers the three tools
├── verifier.py            # core engine: verify_email + clean_email_list
├── disposable_domains.py  # curated disposable-domain set
├── risk_engine.py         # assess_signup_risk heuristics
├── demo.py                # runs all three tools and prints results
├── test_verifier.py       # unit tests (DNS mocked; runs offline)
├── requirements.txt
└── screenshots/           # demo captures (see "Demo" below)
```

---

## Running locally

Requires Python 3.11+.

```bash
pip install -r requirements.txt
python server.py            # starts the MCP server over stdio
```

To see all three tools run without an MCP client (quickest way to review output):

```bash
python demo.py
```

To explore the tools interactively in the MCP Inspector:

```bash
mcp dev server.py
```

### Tests

```bash
python -m unittest        # or: python -m pytest
```

Tests mock the DNS lookup, so they run offline and cover the deterministic logic
(syntax, disposable detection, normalization, dedupe, and risk scoring).

### Using it from an MCP client (e.g. Claude Desktop)

Add an entry to the client's MCP config (`claude_desktop_config.json`), pointing at this folder:

```json
{
  "mcpServers": {
    "inboxvalid": {
      "command": "python",
      "args": ["D:/assignments/context/tvaram_mcp/server.py"]
    }
  }
}
```

Restart the client and the three tools appear in tool discovery.

---

## Example invocations

### `verify_email("founder@gmail.com")`

```json
{
  "email": "founder@gmail.com",
  "status": "valid",
  "reason": "mx_record_found",
  "risk_score": 0.08,
  "checks": { "syntax": true, "disposable": false, "mx": true }
}
```

### `clean_email_list(["founder@gmail.com", "admin@tempmail.com", "bad-email", "founder@gmail.com"])`

```json
{
  "summary": { "total": 4, "valid": 1, "risky": 1, "invalid": 1, "duplicates_removed": 1 },
  "cleaned_list": ["founder@gmail.com"],
  "rejected": [
    { "email": "admin@tempmail.com", "reason": "disposable_domain" },
    { "email": "bad-email", "reason": "invalid_syntax" }
  ]
}
```

### `assess_signup_risk("admin@tempmail.com")`

```json
{
  "email": "admin@tempmail.com",
  "decision": "manual_review",
  "risk_score": 0.7,
  "signals": {
    "valid_syntax": true,
    "disposable_domain": true,
    "role_based_local_part": true,
    "suspicious_local_part": false,
    "mx_present": false
  },
  "recommendation": "Allow signup but flag for manual review or require email verification before activating the account."
}
```

---

## Design decisions

- **`invalid` vs `risky` vs `valid`.** Email verification is probabilistic, so status is three-way.
  Bad syntax is `invalid` — it can never be a real address. A disposable domain or a missing MX
  record is `risky` — the address is well-formed and mail *might* still deliver, so we flag rather
  than reject.
- **Syntax failures are `invalid`.** A malformed string is a hard, deterministic reject; no network
  call needed.
- **Disposable domains are `risky`.** They are syntactically valid burner addresses — low trust, but
  not impossible — so they warrant a flag, not a hard rejection.
- **MX lookup is real, and short-circuited.** We perform an actual DNS MX query (the strongest cheap
  signal that a domain can receive mail) with a 5-second timeout; any DNS failure is treated as
  "no deliverable server." The pipeline stops at the first failing check so `reason` always names the
  real problem.
- **Bulk cleaning reuses the core engine.** `clean_email_list` dedupes on the normalized address and
  calls `verify_email` per unique address — no duplicated validation logic.
- **Signup risk is intentionally heuristic.** `assess_signup_risk` layers simple, additive,
  deterministic weights (role-based, suspicious pattern, disposable, missing MX) on top of the
  verification signals and maps the score to a decision. It is explainable by design, not a black-box
  model.
- **SMTP mailbox verification is intentionally omitted.** Live SMTP probing (RCPT TO) is slow,
  frequently blocked/greylisted, and can harm sender reputation — a poor fit for a fast, safe tool.
  MX + heuristics give most of the signal without those costs.

### Error handling & retry/backoff thinking

- DNS is the only external dependency. `verify_email` never raises on DNS problems: `NXDOMAIN`,
  `NoAnswer`, `NoNameservers`, and timeouts all resolve to a clean `mx=False` / `risky` outcome, so a
  transient failure degrades gracefully instead of crashing the tool.
- The resolver uses a bounded `timeout`/`lifetime` (5s) so a slow domain can't hang an agent.
- Retries are deliberately left out of this prototype to keep behaviour predictable. In production
  the right place for retry-with-exponential-backoff (plus jitter) is around the DNS call, paired with
  a short-TTL cache so repeated lookups of the same domain don't re-query. See Future Improvements.

---

## Future improvements

Signals a production, InboxValid-scale platform would add:

- SMTP mailbox existence verification (RCPT TO probing)
- Catch-all domain detection
- Spam-trap detection
- Richer role-account and disposable-domain lists (regularly updated)
- Async / batched verification for large lists
- Result caching (short-TTL per domain) and retry-with-backoff on DNS
- Rate limiting and per-client quotas

---

## Demo

Screenshots of the tools running in an MCP client live in `screenshots/`:

- `tool-discovery.png` — the three tools listed by the client
- `verify-example.png` — a `verify_email` call and response
- `clean-list-example.png` — a `clean_email_list` call and response
- `signup-risk-example.png` — an `assess_signup_risk` call and response
