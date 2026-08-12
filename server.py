"""InboxValid MCP server.

Exposes email-intelligence tools over the Model Context Protocol (MCP) so that
AI agents / LLM clients can discover and invoke them as structured tools:

    verify_email       -> real-time single-address verification
    clean_email_list   -> bulk list hygiene (dedupe + verify)
    assess_signup_risk -> onboarding / fraud-prevention decision
"""

from mcp.server.fastmcp import FastMCP

# Named server instance; the name is what clients show during tool discovery.
mcp = FastMCP("inboxvalid")


@mcp.tool()
def verify_email(address: str) -> dict:
    """Verify a single email address and return a structured result.

    Returns the email, an overall status (valid/invalid/risky), a machine-readable
    reason, a risk_score, and a per-check breakdown (syntax/disposable/mx).
    """
    return {
        "email": address,
        "status": "unknown",
        "reason": "not_implemented",
    }


@mcp.tool()
def clean_email_list(emails: list[str]) -> dict:
    """Deduplicate and verify a list of emails.

    Returns summary statistics, a cleaned list of usable addresses, and a
    rejected list of addresses that failed with their reasons.
    """
    return {
        "summary": {"total": len(emails)},
        "cleaned_list": [],
        "rejected": [],
        "reason": "not_implemented",
    }


@mcp.tool()
def assess_signup_risk(address: str) -> dict:
    """Assess signup risk for an address and recommend an onboarding decision.

    Returns a decision (allow/verify_email/manual_review/block), a risk_score,
    the signals behind it, and a human-readable recommendation.
    """
    return {
        "email": address,
        "decision": "unknown",
        "reason": "not_implemented",
    }


if __name__ == "__main__":
    # Serve over stdio, which is how MCP clients launch and talk to a local server.
    mcp.run()
