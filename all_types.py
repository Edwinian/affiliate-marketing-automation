from dataclasses import dataclass, fields, is_dataclass
from typing import Any, Dict, List, Optional


class BaseType:
    def to_dict(self) -> Dict[str, Any]:
        """Convert the dataclass instance to a dictionary."""
        result = {}
        for field in fields(self):
            value = getattr(self, field.name)

            # Handle nested dataclasses
            if is_dataclass(value):
                result[field.name] = value.to_dict()

            # Handle lists of dataclasses
            elif isinstance(value, list) and value and is_dataclass(value[0]):
                result[field.name] = [
                    item.to_dict() if is_dataclass(item) else item for item in value
                ]

            # Handle regular lists and other types
            else:
                result[field.name] = value

        return result


@dataclass
class AffiliateLink:
    url: str
    product_title: str
    categories: list[str]
    thumbnail_url: Optional[str] = None
    cta_image_url: Optional[str] = None
    cta_btn_text: Optional[str] = None
    blog_title_prefix: Optional[str] = None


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


@dataclass
class CreateChannelResponse:
    id: str
    url: Optional[str] = None


@dataclass
class UsedLink:
    url: str
    post_id: Optional[str] = None


@dataclass
class Pin:
    id: str
    board_id: str
    title: str
    link: str
    description: str
