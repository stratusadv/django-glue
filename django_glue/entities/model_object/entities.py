from dataclasses import dataclass, asdict
from typing import Any


# This should know all the information about itself.
@dataclass
class GlueModelObject:
    pass


@dataclass
class GlueModelFieldData:
    type: str
    value: Any
    html_attr: dict

    def to_dict(self) -> dict:
        return asdict(self)
