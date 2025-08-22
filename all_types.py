from dataclasses import dataclass
from typing import List, Optional


@dataclass
class AffiliateLink:
    url: str
    category: str
    review_count: Optional[int] = 0


@dataclass
class WordpressCategory:
    id: int
    name: str
    slug: str


@dataclass
class WordpressPost:
    id: int
    title: str
    content: str
    link: str
    date: str
    status: str
    categories: List[WordpressCategory]
