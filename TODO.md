# Django Glue - TODO - Highest to lowest priority

- [ ] Fix proxy delete() actions
- [ ] Add proper seeding to test project
- [ ] Add comprehensive unit tests
- [ ] Add payload validation to actions
- [ ] Add comprehensive docstrings to public APIs
- [ ] Add a proxy for django forms
- [ ] Add ability to glue views (partial page content updates like htmx)
- [ ] Fix debug/production asset loading (currently reversed in `django_glue.html`)
- [ ] Refactor `GlueClient` god class in JavaScript
- [ ] Add JSDoc comments to JavaScript
- [ ] Update docs to reflect new overhauled glue (they currently document the old, pre v1 version which had an entirely different api)
- [ ] Add comprehensive integration testing (cross-stack tests)
- [ ] Add comprehensive e2e testing (using playwright)
- [ ] Document magic numbers (2.2 divisor for keep-alive in `context_processors.py`)
- [ ] Replace pickle with JSON for QuerySet serialization (low risk with proper Django settings)