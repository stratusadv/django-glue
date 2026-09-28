from __future__ import annotations

from functools import partial
from typing import Any

from django_glue.encoders import GlueResponseJSONEncoder
from django_glue.exceptions import GlueComponentRegistrationError


DOM_EVENT_NAMES = frozenset({
    'abort', 'auxclick', 'beforeinput', 'beforematch', 'beforetoggle', 'blur',
    'cancel', 'canplay', 'canplaythrough', 'change', 'click', 'close',
    'contextlost', 'contextmenu', 'contextrestored', 'copy', 'cuechange', 'cut',
    'dblclick', 'drag', 'dragend', 'dragenter', 'dragleave', 'dragover',
    'dragstart', 'drop', 'durationchange', 'emptied', 'ended', 'error', 'focus',
    'formdata', 'input', 'invalid', 'keydown', 'keypress', 'keyup', 'load',
    'loadeddata', 'loadedmetadata', 'loadstart', 'mousedown', 'mouseenter',
    'mouseleave', 'mousemove', 'mouseout', 'mouseover', 'mouseup', 'paste',
    'pause', 'play', 'playing', 'progress', 'ratechange', 'reset', 'resize',
    'scroll', 'scrollend', 'securitypolicyviolation', 'seeked', 'seeking',
    'select', 'slotchange', 'stalled', 'submit', 'suspend', 'timeupdate',
    'toggle', 'volumechange', 'waiting', 'wheel',
    'focusin', 'focusout', 'compositionstart', 'compositionupdate',
    'compositionend', 'selectionchange', 'selectstart',
    'pointerdown', 'pointerup', 'pointermove', 'pointerover', 'pointerout',
    'pointerenter', 'pointerleave', 'pointercancel', 'gotpointercapture',
    'lostpointercapture', 'touchstart', 'touchend', 'touchmove', 'touchcancel',
    'animationstart', 'animationend', 'animationiteration', 'animationcancel',
    'transitionrun', 'transitionstart', 'transitionend', 'transitioncancel',
    'fullscreenchange', 'fullscreenerror', 'beforeunload', 'unload',
    'hashchange', 'popstate', 'pageshow', 'pagehide', 'message',
    'messageerror', 'online', 'offline', 'storage', 'visibilitychange',
})


def is_reserved_event_name(name: str) -> bool:
    return name in DOM_EVENT_NAMES or name.startswith('$')


def emit_event(instance: Any, name: str, detail: dict[str, Any]) -> None:
    if '$address' in detail:
        raise ValueError('Event detail cannot define the reserved $address key.')
    GlueResponseJSONEncoder().encode(detail)
    owner = getattr(instance, '_glue_event_owner', instance)
    owner.__dict__.setdefault('_pending_events', []).append({
        'name': name,
        'detail': detail,
    })


class GlueEvent:
    def __init__(self) -> None:
        self.name: str | None = None

    def __set_name__(self, owner: type, name: str) -> None:
        if is_reserved_event_name(name):
            raise GlueComponentRegistrationError(
                f'Glue event {name!r} conflicts with a browser event or reserved name.'
            )
        self.name = name

    def __get__(self, instance: Any, owner: type | None = None) -> Any:
        if instance is None:
            return self
        return partial(self.emit, instance)

    def emit(self, instance: Any, **detail: Any) -> None:
        emit_event(instance, self.name, detail)
