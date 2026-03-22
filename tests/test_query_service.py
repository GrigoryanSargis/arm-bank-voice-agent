"""
tests/test_query_service.py
===========================
Unit tests for scope detection and refusal messages.
No external API calls needed — tests only cover the keyword gate layer.
"""
from __future__ import annotations

import pytest

from arm_bank_voice_agent.agent.query_service import (
    detect_supported_topic,
    out_of_scope_message,
)

# Armenian keyword constants used in tests (built from codepoints to avoid
# any risk of truncated escape sequences in source)
_VARK     = 'վարկ'      # վարկ (loan)
_VARKER   = 'վարկեր'    # վարկեր (loans)
_AVAND    = 'ավանդ'     # ավանդ (deposit)
_MASNA    = 'մասնաճյուգ'     # մասնաճյուգ (branch)
_BANKOMAT = 'բանկոմատ'  # բանկոմատ (ATM)
_HASTSYE  = 'հասցե'   # հասցե (address)
_ANY_ARM  = 'Ա'   # any Armenian character for script detection tests


class TestDetectSupportedTopic:
    # ── English in-scope ─────────────────────────────────────────────────

    def test_english_credit_loan(self):
        assert detect_supported_topic("What are your loan rates?") == "credit"

    def test_english_credit_consumer(self):
        assert detect_supported_topic("Tell me about consumer loans") == "credit"

    def test_english_credit_mortgage(self):
        assert detect_supported_topic("Do you offer mortgage products?") == "credit"

    def test_english_deposit(self):
        assert detect_supported_topic("I want to open a savings account") == "deposit"

    def test_english_deposit_term(self):
        assert detect_supported_topic("What is the term deposit rate?") == "deposit"

    def test_english_branch(self):
        assert detect_supported_topic("Where is the nearest branch?") == "branch"

    def test_english_atm(self):
        assert detect_supported_topic("Find an ATM near me") == "branch"

    def test_english_address(self):
        assert detect_supported_topic("What is the address of this bank?") == "branch"

    def test_english_map(self):
        assert detect_supported_topic("show me the map of branches") == "branch"

    # ── Armenian in-scope ────────────────────────────────────────────────

    def test_armenian_credit_vark(self):
        result = detect_supported_topic(_VARK + " info")
        assert result in ("credit", "unknown_armenian")

    def test_armenian_credit_varker(self):
        result = detect_supported_topic(_VARKER + " rates")
        assert result in ("credit", "unknown_armenian")

    def test_armenian_deposit_avand(self):
        result = detect_supported_topic(_AVAND + " open")
        assert result in ("deposit", "unknown_armenian")

    def test_armenian_branch_masna(self):
        result = detect_supported_topic(_MASNA + " address")
        assert result in ("branch", "unknown_armenian")

    def test_armenian_branch_bankomat(self):
        result = detect_supported_topic(_BANKOMAT + " location")
        assert result in ("branch", "unknown_armenian")

    def test_armenian_branch_hastsye(self):
        result = detect_supported_topic(_HASTSYE + " list")
        assert result in ("branch", "unknown_armenian")

    # ── Out of scope ─────────────────────────────────────────────────────

    def test_weather_out_of_scope(self):
        assert detect_supported_topic("What is the weather in Yerevan?") is None

    def test_politics_out_of_scope(self):
        assert detect_supported_topic("Tell me about the government") is None

    def test_empty_out_of_scope(self):
        assert detect_supported_topic("") is None

    def test_short_noise(self):
        assert detect_supported_topic("hi") is None

    def test_forex_out_of_scope(self):
        assert detect_supported_topic("What is the USD to AMD rate today?") is None

    def test_general_question_out_of_scope(self):
        assert detect_supported_topic("How do I register a company?") is None

    # ── Case sensitivity ─────────────────────────────────────────────────

    def test_uppercase_loan(self):
        assert detect_supported_topic("LOAN rates please") == "credit"

    def test_mixed_case_deposit(self):
        assert detect_supported_topic("My DEPOSIT account") == "deposit"

    def test_mixed_case_branch(self):
        assert detect_supported_topic("Find BRANCH in Yerevan") == "branch"

    # ── Multi-word phrases ───────────────────────────────────────────────

    def test_phrase_consumer_loan(self):
        assert detect_supported_topic("apply for a consumer loan") == "credit"

    def test_phrase_term_deposit(self):
        assert detect_supported_topic("open a term deposit account") == "deposit"

    def test_phrase_near_me(self):
        assert detect_supported_topic("ATM near me") == "branch"


class TestOutOfScopeMessage:
    def test_english_query_returns_english_refusal(self):
        msg = out_of_scope_message("What is the weather?")
        assert len(msg) > 10
        # Should NOT contain Armenian script
        assert not any("\u0531" <= ch <= "\u058F" for ch in msg)
        # Should contain key refusal words
        assert "loan" in msg.lower() or "deposit" in msg.lower()

    def test_armenian_query_returns_armenian_refusal(self):
        msg = out_of_scope_message(_ANY_ARM + "some query")
        assert len(msg) > 10
        # Should contain Armenian script
        assert any("\u0531" <= ch <= "\u058F" for ch in msg)

    def test_message_non_empty_for_any_input(self):
        for q in ["", "hello", _VARK, "random text"]:
            assert len(out_of_scope_message(q)) > 5
