"""Unit tests for the verification, cleaning, and risk logic.

DNS is mocked so the deterministic logic can be tested offline and fast; the
real MX lookup itself is thin and covered by the demo. Run with:

    python -m pytest        # or:  python -m unittest
"""

import unittest
from unittest.mock import patch

import risk_engine
import verifier


class VerifyEmailTests(unittest.TestCase):
    def test_invalid_syntax_is_invalid(self):
        result = verifier.verify_email("bad-email")
        self.assertEqual(result["status"], "invalid")
        self.assertEqual(result["reason"], "invalid_syntax")
        self.assertEqual(result["risk_score"], 1.0)

    def test_disposable_domain_is_risky(self):
        result = verifier.verify_email("admin@tempmail.com")
        self.assertEqual(result["status"], "risky")
        self.assertEqual(result["reason"], "disposable_domain")
        self.assertTrue(result["checks"]["disposable"])

    def test_address_is_normalized(self):
        # Whitespace + case should not change the outcome or stored email.
        with patch.object(verifier, "_has_mx_record", return_value=True):
            result = verifier.verify_email("  Founder@Gmail.COM  ")
        self.assertEqual(result["email"], "founder@gmail.com")
        self.assertEqual(result["status"], "valid")

    def test_valid_when_mx_present(self):
        with patch.object(verifier, "_has_mx_record", return_value=True):
            result = verifier.verify_email("user@example.com")
        self.assertEqual(result["status"], "valid")
        self.assertEqual(result["reason"], "mx_record_found")

    def test_risky_when_mx_absent(self):
        with patch.object(verifier, "_has_mx_record", return_value=False):
            result = verifier.verify_email("user@example.com")
        self.assertEqual(result["status"], "risky")
        self.assertEqual(result["reason"], "mx_record_not_found")


class CleanEmailListTests(unittest.TestCase):
    def test_dedupe_and_bucketing(self):
        with patch.object(verifier, "_has_mx_record", return_value=True):
            result = verifier.clean_email_list(
                [
                    "founder@gmail.com",
                    "admin@tempmail.com",
                    "bad-email",
                    "founder@gmail.com",
                ]
            )
        self.assertEqual(
            result["summary"],
            {"total": 4, "valid": 1, "risky": 1, "invalid": 1, "duplicates_removed": 1},
        )
        self.assertEqual(result["cleaned_list"], ["founder@gmail.com"])

    def test_dedupe_uses_normalized_form(self):
        with patch.object(verifier, "_has_mx_record", return_value=True):
            result = verifier.clean_email_list(["a@x.com", "A@x.com ", "a@x.com"])
        self.assertEqual(result["summary"]["duplicates_removed"], 2)
        self.assertEqual(result["cleaned_list"], ["a@x.com"])


class SignupRiskTests(unittest.TestCase):
    def test_invalid_syntax_blocks(self):
        result = risk_engine.assess_signup_risk("bad-email")
        self.assertEqual(result["decision"], "block")
        self.assertEqual(result["risk_score"], 1.0)

    def test_clean_personal_address_is_allowed(self):
        with patch.object(verifier, "_has_mx_record", return_value=True):
            result = risk_engine.assess_signup_risk("jane@example.com")
        self.assertEqual(result["decision"], "allow")

    def test_disposable_role_account_goes_to_manual_review(self):
        result = risk_engine.assess_signup_risk("admin@tempmail.com")
        self.assertEqual(result["decision"], "manual_review")
        self.assertTrue(result["signals"]["disposable_domain"])
        self.assertTrue(result["signals"]["role_based_local_part"])

    def test_suspicious_local_part_requires_verification(self):
        with patch.object(verifier, "_has_mx_record", return_value=True):
            result = risk_engine.assess_signup_risk("test123@example.com")
        self.assertEqual(result["decision"], "verify_email")
        self.assertTrue(result["signals"]["suspicious_local_part"])


if __name__ == "__main__":
    unittest.main()
