from typing import Any, Dict

from filter.extension import ExtensionFilter
from filter.base import Filter, FilterBundle
from filter.type import FilterType

class FilterFactory:
    _getters = {
        FilterType.EXTENSION: ExtensionFilter.from_data
    }
    
    @staticmethod
    def get(filter: FilterBundle) -> Filter:
        if "inverted" in filter:
            inverted = filter["inverted"]
        else:
            inverted = False
        return FilterFactory._getters[filter["type"]](inverted, filter["params"])