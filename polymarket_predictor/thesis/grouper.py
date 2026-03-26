"""Group related markets and generate thesis questions.

Three group patterns:
1. DATE TIERS: Same event, different deadlines
   "US Iran ceasefire by April 7/15/30, May 31, June 30, Dec 31"
   Thesis: "When will Iran ceasefire happen?"

2. PRICE TIERS: Same asset, different price levels
   "Crude Oil hit HIGH $80/$90/$100/$110/$120"
   Thesis: "Where is crude oil heading?"

3. STAGE TIERS: Same person/entity, different stages
   "Newsom wins nomination" + "Newsom wins election"
   Thesis: "How strong is Newsom's candidacy?"
"""

import re
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class MarketGroup:
    """A group of related markets sharing a common thesis."""
    group_id: str           # Unique identifier for the group
    thesis_question: str    # The underlying question to predict
    group_type: str         # "date_tier", "price_tier", "stage_tier"
    markets: list = field(default_factory=list)  # List of market objects

    # Thesis prediction (filled after deep prediction)
    thesis_prediction: float | None = None  # The core probability/direction
    thesis_confidence: str = ""
    thesis_reasoning: str = ""

    def to_dict(self) -> dict:
        return {
            "group_id": self.group_id,
            "thesis_question": self.thesis_question,
            "group_type": self.group_type,
            "num_markets": len(self.markets),
            "thesis_prediction": self.thesis_prediction,
            "thesis_confidence": self.thesis_confidence,
        }


class MarketGrouper:
    """Group related Polymarket markets into thesis groups."""

    def group_markets(self, markets: list) -> list[MarketGroup]:
        """Group a list of markets into thesis groups.

        Markets that don't belong to any group are returned as single-market groups.
        """
        groups = []
        used_slugs = set()

        # Pass 1: Find date tier groups (same event, different dates)
        date_groups = self._find_date_tiers(markets)
        for group in date_groups:
            groups.append(group)
            for m in group.markets:
                used_slugs.add(m.slug)

        # Pass 2: Find price tier groups (same asset, different prices)
        remaining = [m for m in markets if m.slug not in used_slugs]
        price_groups = self._find_price_tiers(remaining)
        for group in price_groups:
            groups.append(group)
            for m in group.markets:
                used_slugs.add(m.slug)

        # Pass 3: Find stage tier groups (nomination -> election)
        remaining = [m for m in markets if m.slug not in used_slugs]
        stage_groups = self._find_stage_tiers(remaining)
        for group in stage_groups:
            groups.append(group)
            for m in group.markets:
                used_slugs.add(m.slug)

        # Pass 4: Ungrouped markets become single-market groups
        for m in markets:
            if m.slug not in used_slugs:
                groups.append(MarketGroup(
                    group_id=m.slug,
                    thesis_question=m.question,
                    group_type="single",
                    markets=[m],
                ))

        logger.info("Grouped %d markets into %d groups (%d multi-tier, %d single)",
                    len(markets), len(groups),
                    sum(1 for g in groups if len(g.markets) > 1),
                    sum(1 for g in groups if len(g.markets) == 1))

        return groups

    def _find_date_tiers(self, markets: list) -> list[MarketGroup]:
        """Find markets that are the same event with different date deadlines."""
        # Pattern: slug contains date-like suffixes (by-april-7, by-march-31, etc.)
        # Strategy: strip the date suffix and group by common prefix

        date_patterns = [
            r'-by-(?:january|february|march|april|may|june|july|august|september|october|november|december)-\d+',
            r'-by-\w+-\d{1,2}-\d{4}',
            r'-\d{4}-\d{2}-\d{2}',
            r'-(?:march|april|may|june|july|august|september|october|november|december)-\d{1,2}(?:-\d+)?$',
        ]

        stems = {}  # stem -> [markets]

        for m in markets:
            slug = m.slug
            stem = slug

            # Try to extract a date-free stem
            for pattern in date_patterns:
                stripped = re.sub(pattern, '', slug)
                if stripped != slug and len(stripped) > 5:
                    stem = stripped
                    break

            # Also try: remove trailing numbers that look like date codes
            # "us-x-iran-ceasefire-by-april-7-278" -> "us-x-iran-ceasefire-by"
            # But keep "will-crude-oil-cl-hit-high-100" as is (that's a price)
            cleaned = re.sub(r'-\d{2,}$', '', stem)  # Remove trailing long numbers (IDs)
            if len(cleaned) > 5:
                stem = cleaned

            if stem not in stems:
                stems[stem] = []
            stems[stem].append(m)

        groups = []
        for stem, mlist in stems.items():
            if len(mlist) >= 2:
                # Generate thesis question from the common question pattern
                questions = [m.question for m in mlist]
                thesis = self._extract_common_thesis(questions, "date")

                groups.append(MarketGroup(
                    group_id=f"date_{stem}",
                    thesis_question=thesis,
                    group_type="date_tier",
                    markets=mlist,
                ))

        return groups

    def _find_price_tiers(self, markets: list) -> list[MarketGroup]:
        """Find markets that are the same asset with different price targets."""
        # Pattern: "Will Crude Oil hit (HIGH) $100" and "Will Crude Oil hit (HIGH) $110"
        # Strategy: strip the price and group by common prefix

        stems = {}

        for m in markets:
            slug = m.slug
            # Remove price-like patterns from slug
            # "will-crude-oil-cl-hit-high-100-by-end-of-march-658-396" -> "will-crude-oil-cl-hit-high-by-end-of-march"
            stripped = re.sub(r'-\d+k?(?=-|$)', '', slug)
            # Remove trailing ID numbers
            stripped = re.sub(r'(?:-\d{3,})+$', '', stripped)

            if stripped != slug and len(stripped) > 10:
                if stripped not in stems:
                    stems[stripped] = []
                stems[stripped].append(m)

        groups = []
        for stem, mlist in stems.items():
            if len(mlist) >= 2:
                thesis = self._extract_common_thesis([m.question for m in mlist], "price")

                groups.append(MarketGroup(
                    group_id=f"price_{stem}",
                    thesis_question=thesis,
                    group_type="price_tier",
                    markets=mlist,
                ))

        return groups

    def _find_stage_tiers(self, markets: list) -> list[MarketGroup]:
        """Find markets for the same person/entity at different stages."""
        # Pattern: "X wins nomination" + "X wins election"
        # Strategy: extract person name, group if same person

        person_markets = {}

        for m in markets:
            q = m.question.lower()
            # Extract person name patterns
            match = re.search(r'will\s+(.+?)\s+win\s+the\s+\d{4}', q)
            if match:
                person = match.group(1).strip()
                if person not in person_markets:
                    person_markets[person] = []
                person_markets[person].append(m)

        groups = []
        for person, mlist in person_markets.items():
            if len(mlist) >= 2:
                groups.append(MarketGroup(
                    group_id=f"stage_{person.replace(' ', '_')}",
                    thesis_question=f"How strong is {person.title()}'s candidacy and chances?",
                    group_type="stage_tier",
                    markets=mlist,
                ))

        return groups

    def _extract_common_thesis(self, questions: list[str], group_type: str) -> str:
        """Extract a thesis question from a group of related market questions."""
        if not questions:
            return "Unknown thesis"

        if group_type == "date":
            # "US x Iran ceasefire by April 7?" -> "When will US-Iran ceasefire happen, if at all?"
            # Find the common part before the date
            base = questions[0]
            # Remove date parts
            base = re.sub(r'\b(?:by|before|after)\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:,?\s*\d{4})?\??', '', base, flags=re.IGNORECASE).strip()
            base = re.sub(r'\s+', ' ', base).strip().rstrip('?').strip()
            return f"When will '{base}' happen, if at all? What is the timeline probability?"

        elif group_type == "price":
            # "Will Crude Oil hit $100?" -> "Where is crude oil price heading?"
            base = questions[0]
            base = re.sub(r'\$[\d,]+k?', '[PRICE]', base)
            base = re.sub(r'\(HIGH\)|\(LOW\)', '', base, flags=re.IGNORECASE).strip()
            base = re.sub(r'\s+', ' ', base).strip().rstrip('?').strip()
            return f"Where is the price heading for '{base}'? What price range is most likely?"

        return questions[0]
