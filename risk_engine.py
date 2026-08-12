"""Signup-risk assessment.

Turns the technical verification signals from `verify_email` into a business
decision for onboarding: allow the signup, ask for email confirmation, send it
to manual review, or block it. The scoring is a simple additive heuristic so
every decision can be traced back to the signals that caused it.
"""

from verifier import verify_email

# Local parts that usually belong to a team/mailbox rather than a person.
# Not inherently bad, but higher risk for individual-account signup flows.
ROLE_BASED = {
    "admin",
    "support",
    "info",
    "sales",
    "contact",
    "noreply",
    "no-reply",
    "billing",
    "help",
}

# How much each signal adds to the risk score (0 = safe, 1 = certainly bad).
_WEIGHT_DISPOSABLE = 0.5
_WEIGHT_NO_MX = 0.45
_WEIGHT_ROLE_BASED = 0.2
_WEIGHT_SUSPICIOUS = 0.3

# Score thresholds that map a risk score onto a decision.
_THRESHOLD_BLOCK = 0.8
_THRESHOLD_MANUAL_REVIEW = 0.5
_THRESHOLD_VERIFY = 0.25

_RECOMMENDATIONS = {
    "allow": "Low risk. Allow the signup to proceed normally.",
    "verify_email": "Send a confirmation email and require verification before granting full access.",
    "manual_review": "Allow signup but flag for manual review or require email verification before activating the account.",
    "block": "High risk. Block this signup or require strong manual verification.",
}


def _looks_random(local_part: str) -> bool:
    """Rough guess at machine-generated local parts.

    Long strings with very few vowels (e.g. "xk7fq9zldm") tend to be random or
    bot-generated. Deliberately conservative to avoid flagging normal names.
    """
    if len(local_part) < 10:
        return False
    vowels = sum(char in "aeiou" for char in local_part)
    return vowels / len(local_part) < 0.2


def _is_suspicious(local_part: str) -> bool:
    """Flag throwaway-looking local parts (test accounts or random strings)."""
    return "test" in local_part or _looks_random(local_part)


def _decision_for(score: float) -> str:
    """Map a numeric risk score onto one of the four onboarding decisions."""
    if score >= _THRESHOLD_BLOCK:
        return "block"
    if score >= _THRESHOLD_MANUAL_REVIEW:
        return "manual_review"
    if score >= _THRESHOLD_VERIFY:
        return "verify_email"
    return "allow"


def assess_signup_risk(address: str) -> dict:
    """Assess signup risk for an address and recommend an onboarding decision.

    Reuses `verify_email` for the technical signals (syntax/disposable/mx) and
    layers on role-based and suspicious-pattern heuristics. Returns the decision,
    the risk score, the signals behind it, and a human-readable recommendation.
    """
    verification = verify_email(address)
    email = verification["email"]
    checks = verification["checks"]
    local_part = email.split("@", 1)[0] if "@" in email else email

    # A malformed address can't be contacted at all: block outright.
    if verification["status"] == "invalid":
        return {
            "email": email,
            "decision": "block",
            "risk_score": 1.0,
            "signals": {
                "valid_syntax": False,
                "disposable_domain": False,
                "role_based_local_part": False,
                "suspicious_local_part": False,
                "mx_present": False,
            },
            "recommendation": "Invalid email syntax. Reject and ask the user to re-enter their address.",
        }

    # Ignore any "+tag" when matching role accounts (admin+test@ is still admin).
    role_base = local_part.split("+", 1)[0]
    disposable_domain = checks["disposable"]
    mx_present = checks["mx"]
    role_based = role_base in ROLE_BASED
    suspicious = _is_suspicious(local_part)

    # Add up the risk contributions; a disposable domain already implies no
    # deliverable mailbox, so we don't also charge the missing-MX penalty.
    score = 0.0
    if disposable_domain:
        score += _WEIGHT_DISPOSABLE
    elif not mx_present:
        score += _WEIGHT_NO_MX
    if role_based:
        score += _WEIGHT_ROLE_BASED
    if suspicious:
        score += _WEIGHT_SUSPICIOUS

    score = round(min(score, 1.0), 2)
    decision = _decision_for(score)

    return {
        "email": email,
        "decision": decision,
        "risk_score": score,
        "signals": {
            "valid_syntax": True,
            "disposable_domain": disposable_domain,
            "role_based_local_part": role_based,
            "suspicious_local_part": suspicious,
            "mx_present": mx_present,
        },
        "recommendation": _RECOMMENDATIONS[decision],
    }
