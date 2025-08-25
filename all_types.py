from dataclasses import dataclass
from typing import List


@dataclass
class AffiliateLink:
    url: str
    categories: list[str]


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


@dataclass
class WordpressTag:
    id: int
    name: str
