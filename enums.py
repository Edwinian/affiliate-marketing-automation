from enum import Enum
from typing import Any


class StrEnum(str, Enum):
    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}.{self.name}"

    @classmethod
    def __get_validators__(cls) -> Any:
        yield cls.validate

    @classmethod
    def validate(cls, v: Any) -> Any:
        if not isinstance(v, (str, cls)):
            raise TypeError(f"Value {v} is not a valid {cls.__name__}")
        if isinstance(v, cls):
            return v
        try:
            return cls(v)
        except ValueError:
            raise ValueError(f"Invalid value {v} for {cls.__name__}")


class CustomLinksKey(StrEnum):
    DEFAULT = "default_affiliate_links"
    AMAZON = "amazon_affiliate_links"


class LlmErrorPrompt(StrEnum):
    QUOTA_EXCEEDED = "insufficient credits"
    LENGTH_EXCEEDED = "prompt length exceeded"
