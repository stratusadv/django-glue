from __future__ import annotations

import json


def get_request_body_data(request, key: str = None):
    data = json.loads(request.body.decode('utf-8'))
    return data if key is None else data.get(key, None)


def get_inheritors(cls):
    subclasses = set()
    work = [cls]
    while work:
        parent = work.pop()
        for child in parent.__subclasses__():
            if child not in subclasses:
                subclasses.add(child)
                work.append(child)
    return subclasses