from dataclasses import dataclass


@dataclass
class AmazonAffiliateLink:
    url: str
    review_count: int
    category: str
