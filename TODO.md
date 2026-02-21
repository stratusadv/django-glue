# Django Glue - TODO

## Medium (Quality)
- [ ] Update docs to reflect new overhauled glue (they currently document the old, pre v1 version which had an entirely different api)
- [ ] Add payload validation to actions
- [ ] Add comprehensive docstrings to public APIs
- [ ] Switch from `print()` to Django logging in `views.py`
- [ ] Add comprehensive unit, integration, and e2e testing (using playwright for e2e)
- [ ] Refactor `GlueClient` god class in JavaScript

## Low (Polish)
- [ ] Add JSDoc comments to JavaScript
- [ ] Fix debug/production asset loading (currently reversed in `django_glue.html`)
- [ ] Document magic numbers (2.2 divisor for keep-alive in `context_processors.py`)

## Deferred
- [ ] Replace pickle with JSON for QuerySet serialization (low risk with proper Django settings)