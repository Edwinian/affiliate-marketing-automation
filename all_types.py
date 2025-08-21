from dataclasses import dataclass


@dataclass
class AffiliateLink:
    url: str
    review_count: int
    category: str
