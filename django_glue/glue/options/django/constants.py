from __future__ import annotations

# Model field internal types that Glue never serializes -- applies to plain
# model-object serialization and to related-model choice output alike.
DEFAULT_EXCLUDED_MODEL_FIELD_TYPES = frozenset({
    'BinaryField',
})

# Default cap on how many matches a searchable Glue.choices() source returns
# per query. Also the default for the public Glue.choices(search_limit=...) arg.
DEFAULT_SEARCH_LIMIT = 25

# Attribute name under which a configured queryset's QuerySetChoiceOptions is
# stashed on its Django Query, so the configuration survives queryset cloning
# and ModelChoiceField assignment.
QUERYSET_CHOICE_OPTIONS_ATTRIBUTE = '_django_glue_queryset_choice_options'
