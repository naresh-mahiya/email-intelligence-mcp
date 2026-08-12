"""Standalone demo of the three email-intelligence tools.

Runs each tool against a few illustrative addresses and prints the structured
results, so the behaviour can be reviewed without an MCP client. The MX lookups
are real, so this needs an internet connection.

    python demo.py
"""

import json

from risk_engine import assess_signup_risk
from verifier import clean_email_list, verify_email


def _show(title: str, result: dict) -> None:
    print(f"\n# {title}")
    print(json.dumps(result, indent=2))


def main() -> None:
    print("=== verify_email ===")
    for address in ["founder@gmail.com", "admin@tempmail.com", "bad-email"]:
        _show(f"verify_email({address!r})", verify_email(address))

    print("\n=== clean_email_list ===")
    _show(
        "clean_email_list([...])",
        clean_email_list(
            [
                "founder@gmail.com",
                "admin@tempmail.com",
                "bad-email",
                "founder@gmail.com",
            ]
        ),
    )

    print("\n=== assess_signup_risk ===")
    for address in ["founder@gmail.com", "admin@tempmail.com", "test123@gmail.com"]:
        _show(f"assess_signup_risk({address!r})", assess_signup_risk(address))


if __name__ == "__main__":
    main()
