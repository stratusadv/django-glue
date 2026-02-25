# Django Glue - TODO - Highest to lowest priority
 
- [ ] Change GlueFormProxy so that the field property is at the top level and value, label, errors etc. are all children
- [ ] Add comprehensive integration testing (cross-stack tests)
- [ ] Add comprehensive e2e testing (using playwright)
- [ ] In form proxy use field definition labels for the test project html labels
- [ ] Refactor `GlueClient` god class in JavaScript
- [ ] Split test project sections into separate views
- [ ] Add detailed comments to test_project to document usage better
- [ ] Add JSDoc comments to JavaScript
- [ ] Consider adding ability partial page content updates like htmx - evaluate this against the option of just using htmx
- [ ] Update docs to reflect new overhauled glue (they currently document the old, pre v1 version which had an entirely different api)
- [ ] Document magic numbers (2.2 divisor for keep-alive in `context_processors.py`)
- [ ] Replace pickle with JSON for QuerySet serialization (low risk with proper Django settings)