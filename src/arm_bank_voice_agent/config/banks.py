from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

BankName = Literal["Ardshinbank", "Inecobank", "Mellat Bank", "Evocabank"]
Topic = Literal["credit", "deposit", "branch"]


@dataclass(frozen=True)
class SeedPage:
    topic: Topic
    url: str
    language: str = "en"
    subtopic: str | None = None
    section_path: list[str] = field(default_factory=list)
    # CSS selector to wait for before extracting — for JS-heavy pages
    wait_for_selector: str | None = None


@dataclass(frozen=True)
class BankConfig:
    name: BankName
    allowed_domains: tuple[str, ...]
    seed_pages: tuple[SeedPage, ...]


BANKS: dict[str, BankConfig] = {
    "ardshinbank": BankConfig(
        name="Ardshinbank",
        allowed_domains=("ardshinbank.am", "www.ardshinbank.am"),
        seed_pages=(
            SeedPage(
                topic="credit",
                url="https://ardshinbank.am/for-you/consumer-loans?lang=en",
                language="en",
                subtopic="consumer_loan",
            ),
            # Deposit page redirects — use the direct product page instead
            SeedPage(
                topic="deposit",
                url="https://ardshinbank.am/for-you/demand-deposit?lang=en",
                language="en",
                subtopic="demand_deposit",
            ),
            SeedPage(
                topic="deposit",
                url="https://ardshinbank.am/for-you/term-deposit?lang=en",
                language="en",
                subtopic="term_deposit",
            ),
            SeedPage(
                topic="branch",
                url="https://ardshinbank.am/Information/branch-atm?lang=en",
                language="en",
                subtopic="branches_and_atms",
                # Wait for the branch list container to render
                wait_for_selector=".branch-list, .branches, table, .location",
            ),
        ),
    ),

    "inecobank": BankConfig(
        name="Inecobank",
        allowed_domains=("inecobank.am", "www.inecobank.am"),
        seed_pages=(
            # Use tariff/terms pages — they have actual rate tables
            SeedPage(
                topic="credit",
                url="https://www.inecobank.am/en/Individual/consumer-loans",
                language="en",
                subtopic="consumer_loan",
            ),
            SeedPage(
                topic="credit",
                url="https://www.inecobank.am/hy/Individual/varker/spaooakan-varker",
                language="hy",
                subtopic="consumer_loan_hy",
            ),
            SeedPage(
                topic="deposit",
                url="https://www.inecobank.am/en/Individual/deposits",
                language="en",
                subtopic="deposits",
            ),
            SeedPage(
                topic="deposit",
                url="https://www.inecobank.am/hy/Individual/avandner",
                language="hy",
                subtopic="deposits_hy",
            ),
            SeedPage(
                topic="branch",
                url="https://www.inecobank.am/hy/map/branches",
                language="hy",
                subtopic="branches_map",
                wait_for_selector=".branch-item, .masnahajogh, li",
            ),
        ),
    ),

    "mellat_bank": BankConfig(
        name="Mellat Bank",
        allowed_domains=("mellatbank.am", "www.mellatbank.am"),
        seed_pages=(
            SeedPage(
                topic="credit",
                url="https://mellatbank.am/hy/loans_individual",
                language="hy",
                subtopic="loans_overview",
            ),
            SeedPage(
                topic="credit",
                url="https://mellatbank.am/hy/Mortgage-loan1",
                language="hy",
                subtopic="mortgage",
            ),
            SeedPage(
                topic="deposit",
                url="https://mellatbank.am/hy/Deposits",
                language="hy",
                subtopic="term_deposit",
            ),
            SeedPage(
                topic="branch",
                url="https://mellatbank.am/hy/DepositBox",
                language="hy",
                subtopic="branches",
            ),
        ),
    ),

    "evocabank": BankConfig(
        name="Evocabank",
        allowed_domains=("evocabank.am", "www.evocabank.am"),
        seed_pages=(
            SeedPage(
                topic="credit",
                url="https://evocabank.am/en/loans-to-individuals/housing-mortgage-loans-tariffs-terms-of-provision",
                language="en",
                subtopic="mortgage_tariffs",
            ),
            SeedPage(
                topic="credit",
                url="https://evocabank.am/en/loans-to-individuals/",
                language="en",
                subtopic="loans_overview",
                wait_for_selector=".loan, h2, table",
            ),
            SeedPage(
                topic="deposit",
                url="https://evocabank.am/en/deposits/",
                language="en",
                subtopic="deposits_overview",
            ),
            SeedPage(
                topic="deposit",
                url="https://evocabank.am/en/deposits/evoca-online-deposit/",
                language="en",
                subtopic="online_deposit",
            ),
            SeedPage(
                topic="branch",
                url="https://evocabank.am/en/branches-and-atms/",
                language="en",
                subtopic="branches",
            ),
        ),
    ),
}