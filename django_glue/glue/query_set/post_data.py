from dataclasses import dataclass


@dataclass
class FilterQuerySetGluePostData:
    filter_params: dict[str, str]
