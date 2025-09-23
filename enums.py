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


class ProgramBrand(StrEnum):
    AMAZON = "AMAZON"
    NORD = "VPN"
    FIVERR = "FIVERR"


class LlmErrorPrompt(StrEnum):
    QUOTA_EXCEEDED = "insufficient credits"
    LENGTH_EXCEEDED = "total length exceeded"


class PinterestTrendType(StrEnum):
    QUARTER = "growing"  # high upward growth in search volume over the last quarter
    MONTHLY = "monthly"  # high search volume in the last month
    YEARLY = "yearly"  # high search volume in the last year
    SEASONAL = "seasonal"  # high upward growth in search volume over the last month and exhibit a seasonal recurring pattern


class WordpressPostStatus(StrEnum):
    DRAFT = "draft"
    PENDING = "pending"
    PRIVATE = "private"
    PUBLISH = "publish"
    FUTURE = "future"
