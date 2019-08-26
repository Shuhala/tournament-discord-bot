from dataclasses import dataclass, field
from typing import Optional, List

from ._base import BaseDataClass


@dataclass
class Player(BaseDataClass):
    name: str
    custom_fields: List[str] = field(default_factory=list)
    email: Optional[str] = field(default=None)
