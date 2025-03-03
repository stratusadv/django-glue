from dataclasses import dataclass


@dataclass
class FilterGlueQuerySetPostData:
    filter_params: dict[str, str]
