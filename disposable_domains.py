"""Curated set of known disposable / throwaway email domains.

These are burner-mail providers whose addresses tend to signal low-intent or
throwaway signups. Kept as a small in-memory set for O(1) lookup and easy
auditing; a production system would load a larger, regularly-updated list.
"""

DISPOSABLE_DOMAINS = {
    "tempmail.com",
    "10minutemail.com",
    "mailinator.com",
    "guerrillamail.com",
    "throwawaymail.com",
    "yopmail.com",
    "getnada.com",
    "trashmail.com",
}
