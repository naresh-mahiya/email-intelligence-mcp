"""Core email verification engine.

`verify_email` runs a short, ordered pipeline and returns a structured result.
It is the single source of truth for validation logic; the bulk-cleaning and
signup-risk tools build on top of it rather than re-implementing checks.
"""

import re

import dns.resolver

from disposable_domains import DISPOSABLE_DOMAINS

# Pragmatic email syntax check: one local part, one "@", a dotted domain.
# Deliberately not RFC-exhaustive — it rejects obvious garbage while accepting
# the real-world addresses we then confirm with a DNS lookup.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# DNS lookups can hang; cap how long we wait so the tool stays responsive.
_DNS_TIMEOUT_SECONDS = 5.0

# Deterministic risk scores per outcome (0 = safe, 1 = certainly bad).
_RISK_INVALID_SYNTAX = 1.0
_RISK_DISPOSABLE = 0.75
_RISK_NO_MX = 0.45
_RISK_VALID = 0.08


def _has_mx_record(domain: str) -> bool:
    """Return True if the domain publishes at least one MX record.

    Any resolution failure (no records, unknown domain, timeout, malformed
    domain) is treated as "no deliverable mail server" rather than raising,
    so the caller always gets a clean boolean.
    """
    resolver = dns.resolver.Resolver()
    resolver.timeout = _DNS_TIMEOUT_SECONDS
    resolver.lifetime = _DNS_TIMEOUT_SECONDS
    try:
        answers = resolver.resolve(domain, "MX") # mx for mail exchange
        return len(answers) > 0
    except (
        dns.resolver.NoAnswer,
        dns.resolver.NXDOMAIN,
        dns.resolver.NoNameservers,
        dns.resolver.LifetimeTimeout,
        dns.exception.DNSException,
    ):
        return False


def _result(email: str, status: str, reason: str, risk_score: float,
            syntax: bool, disposable: bool, mx: bool) -> dict:
    """Assemble the structured verification response."""
    return {
        "email": email,
        "status": status,
        "reason": reason,
        "risk_score": risk_score,
        "checks": {
            "syntax": syntax,
            "disposable": disposable,
            "mx": mx,
        },
    }


def verify_email(address: str) -> dict:
    """Verify one email address through syntax, disposable, and MX checks.

    Returns a dict with an overall `status` (valid/invalid/risky), a
    machine-readable `reason`, a deterministic `risk_score`, and the individual
    `checks` that produced it. The pipeline short-circuits at the first failing
    check so the reason always points to the actual problem.
    """
    # Normalize before anything else so all comparisons are consistent.
    email = address.strip().lower()

    # Syntax: a malformed address can never be valid, so this is a hard reject.
    if not _EMAIL_RE.match(email):
        return _result(email, "invalid", "invalid_syntax", _RISK_INVALID_SYNTAX,
                       syntax=False, disposable=False, mx=False)

    domain = email.rsplit("@", 1)[1]

    # Disposable domains are syntactically fine but low-trust: flag as risky,
    # not invalid, since mail may still deliver.
    if domain in DISPOSABLE_DOMAINS:
        return _result(email, "risky", "disposable_domain", _RISK_DISPOSABLE,
                       syntax=True, disposable=True, mx=False)

    # Without an MX record the domain cannot accept mail, but the address itself
    # is well-formed, so treat it as risky rather than outright invalid.
    if not _has_mx_record(domain):
        return _result(email, "risky", "mx_record_not_found", _RISK_NO_MX,
                       syntax=True, disposable=False, mx=False)

    return _result(email, "valid", "mx_record_found", _RISK_VALID,
                   syntax=True, disposable=False, mx=True)


def clean_email_list(emails: list[str]) -> dict:
    """Deduplicate and verify a list of emails for bulk list hygiene.

    Duplicates are collapsed on the normalized form (so "A@x.com" and "a@x.com "
    count once). Each unique address is run through `verify_email`; only `valid`
    addresses make the cleaned list, while `risky` and `invalid` ones are
    rejected with their reason. Returns summary counts, the cleaned list, and
    the rejected entries.
    """
    seen = set()
    unique = []
    duplicates_removed = 0

    # Deduplicate on the normalized address while preserving first-seen order.
    for raw in emails:
        normalized = raw.strip().lower()
        if normalized in seen:
            duplicates_removed += 1
            continue
        seen.add(normalized)
        unique.append(normalized)

    cleaned_list = []
    rejected = []
    counts = {"valid": 0, "risky": 0, "invalid": 0}

    for email in unique:
        result = verify_email(email)
        counts[result["status"]] += 1
        if result["status"] == "valid":
            cleaned_list.append(result["email"])
        else:
            rejected.append({"email": result["email"], "reason": result["reason"]})

    return {
        "summary": {
            "total": len(emails),
            "valid": counts["valid"],
            "risky": counts["risky"],
            "invalid": counts["invalid"],
            "duplicates_removed": duplicates_removed,
        },
        "cleaned_list": cleaned_list,
        "rejected": rejected,
    }
