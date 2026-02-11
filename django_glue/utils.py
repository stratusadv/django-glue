from __future__ import annotations

import builtins


def get_type(type_name):
    try:
        return getattr(builtins, type_name)
    except AttributeError:
        try:
            obj = globals()[type_name]
        except KeyError:
            return None

        return repr(obj) if isinstance(obj, type) else None