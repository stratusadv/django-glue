# ADR 012: FormSetGlue is a keyed collection of FormGlue, not a BaseFormSet

Status: Accepted; implemented on branch (consumer migration deferred to phase 6)

Date: 2026-09-17

## Context

`FormSetGlue` currently wraps a Django `BaseFormSet`. That substrate is the wrong
foundation for a reactive collection:

- `BaseFormSet` is **positional**. Its management form is
  `TOTAL_FORMS` + `{prefix}-{i}-field`, and `_bind_formset` reconstitutes the
  formset from a positional `data` dict. There is no stable per-form identity in
  the framework to lift — a form's only id is its index.
- `BaseFormSet` is **submission-shaped**: take a POST body, validate N forms,
  save them. Glue needs the opposite — N *live* forms that can be added,
  removed, and validated on demand.
- The positional substrate is exactly what forces the "loop index is never a
  key" violation that state-model §8 and ADR 011 forbid: the current formset
  addresses its forms as `form_list.{index}`.

Every attempt to give a form a stable key collides with the formset's positional
`data` binding underneath. The fix is to stop building on `BaseFormSet`.

The actual requirement is not "wrap a Django formset." It is: **a robust way to
add an arbitrary number of objects, each validated through the same form
class.** That is a keyed collection of `FormGlue` children with a shared form
class — structurally the same shape as `SequenceGlue`, whose items happen to be
forms. It composes onto `BaseCollectionGlue` like the other two collection
families (ADR 011, state-model §4 and §8).

## Decision

`FormSetGlue` becomes a `BaseCollectionGlue` whose children are `FormGlue`s. It
wraps **no** `BaseFormSet`. Each child is a standalone Django `Form` already
wrapped in a `FormGlue`; the formset owns the order/membership (the keys) and
the formset-level concerns, and delegates per-form work to the children.

- **Identity** is the formset's construction rules, not a positional buffer:
  `{form_class_path, formset_class_path, min_num, max_num, can_delete}`.
  There is no `prefix`, no management form, and no `extra`. The concrete
  `formset_class_path` is what lets a custom `Glue.FormSet` subclass (with its
  `clean()` override) survive reconstruction; reconstruction resolves that
  class and reads its declared `form_class` from it, falling back to the
  signed `form_class_path` only for the base case (a plain form class, where
  `formset_class_path` is `FormSetGlue` itself).
- **Members** are keyed `FormGlue` children, yielded by `get_keyed_items()` as
  `(key, FormGlue)` pairs (ADR 011). The collection starts **empty**; nothing is
  materialized up front.
- `min_num` / `max_num` are validation floors/ceilings, not "spawn N blank
  forms" counts. A formset below `min_num` or above `max_num` fails validation.

### What we take on when we drop `BaseFormSet`

`BaseFormSet` provided two capabilities that move onto the collection:

1. **Cross-form validation.** Django's `BaseFormSet.clean()` runs after every
   form is cleaned and reports formset-level errors via `non_form_errors()`.
   Glue re-hosts this as an overridable
   `FormSetGlue.clean(forms: list[forms.BaseForm]) -> list[str]`. It receives
   plain Django `Form`s — never `FormGlue`s — so application code stays
   Django-idiomatic and the glue wrapper is hidden.
2. **min/max enforcement.** The collection checks membership against `min_num`
   / `max_num` during validation/admission.

`validate()` chains: validate each child `FormGlue` (per-form errors) → run
`clean()` over the bound Django forms (cross-form errors) → return
`{valid, form_list, non_form_errors}`, the same shape the legacy code emitted.

### The developer contract

A gluable formset is a `Glue.FormSet` subclass (an alias for `FormSetGlue`).
The developer supplies the form class, optional min/max/can_delete defaults,
and an optional cross-form `clean()`:

```python
class BulkTimeEntryFormSet(Glue.FormSet):
    form_class = TimeEntryForm      # required
    min_num = 1                      # defaults, all shortcut-overrideable
    max_num = 50
    can_delete = True

    def clean(self, forms: list[forms.BaseForm]) -> list[str]:  # optional
        primary = [f for f in forms if f.cleaned_data.get('is_primary')]
        return ['Only one entry can be marked primary.'] if len(primary) > 1 else []
```

Registration goes through **one** entrypoint, `Glue.formset` (never
`Glue.glue`). It takes a **class** in both cases and disambiguates by type — a
`Glue.FormSet` subclass is instantiated as-is; a plain Django form class builds
the default formset:

```python
# custom — a Glue.FormSet subclass
Glue.formset(request, 'bulk_time_entries', BulkTimeEntryFormSet, Glue.Access.CHANGE)

# base — a plain Django form class
Glue.formset(request, 'quick_entries', TimeEntryForm, Glue.Access.CHANGE, min_num=0, max_num=10)
```

`min_num`, `max_num`, and `can_delete` resolve in the order **kwarg > class
var > built-in default**, so a shortcut call can override the subclass defaults
without a new class.

## Consequences

- The positional substrate is gone: no management form, no `_bind_formset`
  positional `data` dict, no `form_list.{index}` naming, no `extra`. A form's
  key is its slot in the collection, owned by the collection (ADR 011).
- `FormSetGlue`, `QuerySetGlue`, and `SequenceGlue` all sit on
  `BaseCollectionGlue` with the same `get_keyed_items()` / children-map
  pipeline; the formset's only family-specific surface is its form-class
  identity and cross-form `clean()`.
- Cross-form validation is now an explicit, overridable, application-facing
  method with a Django-idiomatic signature; the framework no longer mediates it.
- `Glue.formset` is the single, type-dispatched entrypoint; the generic
  `Glue.glue` is not a supported path for formsets.
- The consuming portal's `bulk_time_entries` formset migrates from
  `formset_factory(...)` to a `Glue.FormSet` subclass with no behavior change
  to the client.

## Rejected alternatives

- **Keep `BaseFormSet` and key forms by the prefix suffix** (e.g. `form-0` →
  `"0"`). Uniform and pragmatic, but the seeded forms' keys are still derived
  from position, which is the §8 "loop index as key" smell, and every stable
  key diverges from the formset's positional `data` binding.
- **Invent stable generated keys over a `BaseFormSet`.** True to "stable
  membership" but the framework gives no per-form id to back it, so the key and
  the positional data binding can silently disagree.
- **`Glue.glue(request, name, FormSetSubclass(), access)` as the entrypoint.**
  The generic escape hatch leaks the formset's construction into application
  code; a dedicated `Glue.formset` keeps one code path and one mental model.
- **`clean(forms: list[FormGlue])`.** Forces application code through the glue
  wrapper (`f.form.cleaned_data`); the formset should hand the developer plain
  Django forms and hide the `FormGlue` boundary.
