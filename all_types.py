from dataclasses import dataclass
from typing import Optional


@dataclass
class AffiliateLink:
    url: str
    category: str
    review_count: Optional[int] = 0
