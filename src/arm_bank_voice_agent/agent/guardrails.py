from __future__ import annotations

import re
import difflib
from dataclasses import dataclass
from typing import Literal

Topic = Literal["credit", "deposit", "branch", "out_of_scope"]

# ── In-scope keyword sets (English + Armenian) ───────────────────────────────

CREDIT_TERMS = {
    # English
    "credit", "loan", "loans", "consumer", "borrow", "mortgage",
    "overdraft", "lending", "installment",
    # Armenian
    "վարկ", "վարկեր", "ապառիկ", "հիփոթեք", "օվերդրաֆտ",
}

DEPOSIT_TERMS = {
    # English
    "deposit", "deposits", "saving", "savings",
    # Armenian
    "ավանդ", "ավանդներ", "խնայողություն", "խնայողություններ",
}

BRANCH_TERMS = {
    # English
    "branch", "branches", "atm", "atms", "address", "addresses",
    "location", "locations", "map", "office", "offices", "network",
    # Armenian
    "մասնաճյուղ", "մասնաճյուղեր", "բանկոմատ", "բանկոմատներ",
    "հասցե", "հասցեներ", "տեղ", "տեղեր",
}

# ── Bank name aliases (English + Armenian) ───────────────────────────────────

BANK_ALIASES: dict[str, str] = {
    "evocabank": "Evocabank",
    "evoca": "Evocabank",
    "evoca bank": "Evocabank",
    "էվոկա": "Evocabank",
    "էվոկաբանկ": "Evocabank",
    "էվոկա բանկ": "Evocabank",

    "ardshinbank": "Ardshinbank",
    "արդշինբանկ": "Ardshinbank",
    "արդշին բանկ": "Ardshinbank",

    "inecobank": "Inecobank",
    "ineco": "Inecobank",
    "ինեկոբանկ": "Inecobank",
    "ինեկո բանկ": "Inecobank",

    "mellat": "Mellat Bank",
    "mellat bank": "Mellat Bank",
    "mellatbank": "Mellat Bank",
    "մելլաթ": "Mellat Bank",
    "մելլաթ բանկ": "Mellat Bank",
}

# ── Common typos / English misspellings ──────────────────────────────────────

COMMON_TYPOS: dict[str, str] = {
    "luan": "loan",
    "luans": "loans",
    "lon": "loan",
    "lons": "loans",
    "laon": "loan",
    "lone": "loan",

    "depost": "deposit",
    "depoist": "deposit",
    "deposite": "deposit",

    "branh": "branch",
    "branhes": "branches",
    "brunch": "branch",

    "atim": "atm",

    "morgage": "mortgage",
    "morgages": "mortgage",
}

# ── Armenian transliteration / STT variants ──────────────────────────────────
# These help when Armenian speech gets transcribed in Latin letters.

ARMENIAN_STT_VARIANTS: dict[str, str] = {
    # credit / loan
    "vark": "վարկ",
    "varker": "վարկեր",
    "varki": "վարկ",
    "varkeri": "վարկեր",
    "aparik": "ապառիկ",
    "aparik": "ապառիկ",
    "hipotek": "հիփոթեք",
    "hipotekayin": "հիփոթեք",

    # deposit
    "avand": "ավանդ",
    "avandner": "ավանդներ",
    "avandi": "ավանդ",
    "avandneri": "ավանդներ",
    "khnayoghutyun": "խնայողություն",
    "khnayoghutyunner": "խնայողություններ",

    # branch / ATM
    "masnachyugh": "մասնաճյուղ",
    "masnachyugher": "մասնաճյուղեր",
    "masnajyugh": "մասնաճյուղ",
    "masnajyugher": "մասնաճյուղեր",
    "bankomat": "բանկոմատ",
    "bankomatner": "բանկոմատներ",
    "hasce": "հասցե",
    "hascener": "հասցեներ",
    "hasse": "հասցե",
    "tex": "տեղ",
}

_ALL_TERMS = (
    CREDIT_TERMS | DEPOSIT_TERMS | BRANCH_TERMS | set(BANK_ALIASES.keys())
)

@dataclass(frozen=True)
class QueryDecision:
    topic: Topic
    bank: str | None
    should_refuse: bool
    refusal_reason: str | None = None

class QueryGuard:
    def classify(self, query: str) -> QueryDecision:
        normalized = self._normalize(query)
        bank = self._detect_bank(normalized)

        matched: list[Topic] = []

        if self._contains_any(normalized, CREDIT_TERMS):
            matched.append("credit")
        if self._contains_any(normalized, DEPOSIT_TERMS):
            matched.append("deposit")
        if self._contains_any(normalized, BRANCH_TERMS):
            matched.append("branch")

        # If user wrote in Armenian/transliterated Armenian but exact keyword
        # did not match, keep it in scope and let KB/LLM answer.
        if not matched and (_has_armenian(query) or _looks_like_armenian_translit(normalized)):
            matched.append("credit")

        if not matched:
            return QueryDecision(
                topic="out_of_scope",
                bank=bank,
                should_refuse=True,
                refusal_reason=(
                    "Կարող եմ պատասխանել միայն վարկերի, ավանդների, "
                    "մասնաճյուղերի և բանկոմատների վերաբերյալ հարցերին։"
                ),
            )

        return QueryDecision(
            topic=matched[0],
            bank=bank,
            should_refuse=False,
        )

    def _normalize(self, text: str) -> str:
        text = text.lower().strip()
        text = re.sub(r"[^\w\s\u0531-\u058F]", " ", text)
        words = text.split()

        fixed: list[str] = []
        ascii_terms = [t for t in _ALL_TERMS if t.isascii()]

        for word in words:
            if word in ARMENIAN_STT_VARIANTS:
                fixed.append(ARMENIAN_STT_VARIANTS[word])
                continue

            if word in COMMON_TYPOS:
                fixed.append(COMMON_TYPOS[word])
                continue

            if word.isascii() and len(word) >= 4:
                close = difflib.get_close_matches(word, ascii_terms, n=1, cutoff=0.82)
                fixed.append(close[0] if close else word)
            else:
                fixed.append(word)

        return " ".join(fixed)

    def _contains_any(self, text: str, terms: set[str]) -> bool:
        words = set(text.split())
        for term in terms:
            if " " in term:
                if term in text:
                    return True
            else:
                if term in words:
                    return True
        return False

    def _detect_bank(self, normalized_query: str) -> str | None:
        for alias, canonical in BANK_ALIASES.items():
            if alias in normalized_query:
                return canonical
        return None

def _has_armenian(text: str) -> bool:
    return any("\u0531" <= ch <= "\u058F" for ch in text)

def _looks_like_armenian_translit(text: str) -> bool:
    translit_markers = {
        "vark", "avand", "masnachyugh", "bankomat", "hasce", "aparik", "hipotek"
    }
    words = set(text.split())
    return any(marker in words for marker in translit_markers)

def out_of_scope_message(query: str) -> str:
    return (
        "Ներողություն, կարող եմ պատասխանել միայն վարկերի, ավանդների, "
        "մասնաճյուղերի և բանկոմատների վերաբերյալ հարցերին։"
    )