# Django Glue - TODO - Highest to lowest priority

- [ ] Update claude.md
- [ ] Use modelform factory for model field validation
- [ ] Rename GlueProxyFieldsMixin to GlueProxyModelFieldsMixin
- [ ] Add form proxy demo into the test project
- [ ] Fix debug/production asset loading (currently reversed in `django_glue.html`)
- [ ] Refactor `GlueClient` god class in JavaScript
- [ ] Add python test coverage
- [ ] Add comprehensive client unit testing
- [ ] Add comprehensive integration testing (cross-stack tests)
- [ ] Add comprehensive e2e testing (using playwright)
- [ ] Add JSDoc comments to JavaScript
- [ ] Consider adding ability partial page content updates like htmx - evaluate this against the option of just using htmx
- [ ] Update docs to reflect new overhauled glue (they currently document the old, pre v1 version which had an entirely different api)
- [ ] Document magic numbers (2.2 divisor for keep-alive in `context_processors.py`)
- [ ] Replace pickle with JSON for QuerySet serialization (low risk with proper Django settings)