# ADR 051: A Form Field Is An Attribute's Type

Status: Proposed

Date: 2026-11-22

## Context

ADR 042 gave every declaration one `GlueSerializer`, and declined "a single
form field as an attribute's type" because "a one-field form covers it, and
keeps one way to declare form-shaped state."

That one-field form is now the common case. Profitly's named-record lists
(customers, vendors, products) are sorted by one value, and declare a form for
it:

```python
class NameSortForm(forms.Form):
    sort = forms.ChoiceField(choices=NameSortChoices.choices, initial=NameSortChoices.NAME)

class BaseNameSortedListComponent(ModelCrudScrollComponent):
    filters: NameSortForm = Glue.attr(editable=True)

    def get_queryset(self):
        sort = NameSortChoices(self.filters.cleaned_data['sort']) if self.filters.is_valid() else NameSortChoices.NAME
```

A class, a validation, a dictionary read and a conversion hold one choice.

The alternatives that exist each lack one half:

- **A typed attribute** (`sort: NameSortChoices = Glue.attr(NameSortChoices.NAME, editable=True)`)
  is loaded by pydantic, which refuses an unknown value, but it sends the
  browser nothing to draw a control from: no label, no choices, no
  `required`. Spire's field includes, such as its choice field, read exactly
  those.
- **A form held as state** sends them, but is the class above.

Glue already has both halves of a field as a value:

- `FormFieldSerializer` claims any `forms.Field` as a declaration's target,
  and an attribute's `value_type` names the target of a declaration built
  without a type hint, so `value_type=forms.TypedChoiceField(...)` already
  resolves it. It loads a raw value unchanged, for the form it sits in to
  clean.
- `field_schema()` describes a form field to the browser, as a form's fields
  are described.

## Decision

A component's value attribute may be declared with a Django form field as its
type. The field validates and converts the value, and describes it to the
browser, as it would inside a form.

```python
class BaseNameSortedListComponent(ModelCrudScrollComponent):
    sort = Glue.ComponentField(forms.TypedChoiceField(
        choices=NameSortChoices.choices,
        coerce=NameSortChoices,
        initial=NameSortChoices.NAME,
    ))

    def get_queryset(self):
        return queryset.order_by(*ORDERS[self.sort])     # a NameSortChoices
```

```django
{% include 'django_spire/glue/form/field/choice/field.html' with glue_field='component.sort' %}
```

1. **`Glue.ComponentField(field)` declares it, and the field says all of it.** The
   field's `initial` is the value's default, called when it is a callable, as
   a `default_factory` is. The value is editable unless the field is
   `disabled`, which is also what its description tells the browser. A
   required field with no `initial` is refused, since the value would start as
   one the field refuses. `Glue.ComponentField` takes only a form field and no other
   option, so a default or an editability can't be stated twice and disagree.
   Underneath, the field is the declaration's `value_type`, the target Glue
   already resolves a serializer from; `value_type` stays Glue's own plumbing,
   which application code doesn't write.

2. **The attribute holds the field's cleaned value.** Python reads and
   assigns what `field.clean()` returns, such as a `NameSortChoices`, a
   `date` or a `Decimal`. The browser and the token hold what
   `field.prepare_value()` makes of it, as a form's bound field shows it. A
   value from the browser is loaded with `field.clean()`, and one restored
   from the token the same way. The default is held as cleaned too.

3. **A value the field refuses is refused as an update.** `clean()`'s
   `ValidationError` is the serializer's error, so the call is refused as an
   update a typed attribute's pydantic refuses. There is no per-attribute
   error: a control drawn from the field's choices or type sends only what
   the field accepts, so a refused value comes from a crafted request. A value
   a user may get wrong belongs in a form, whose errors are shown.

4. **The browser gets the field's description.** The attribute's presentation
   is `field_schema(field, editable=...)`: label, `required`, help text,
   choices, lengths. A component's proxy gains `$fields`, as a form's and a
   model's have, so `component.$fields.sort` is the attribute's description
   and Spire's field includes bind `glue_field='component.sort'` as they bind
   a form's field.

5. **The fields a value can't stand alone in are refused when the class is
   defined.** A field over a queryset (`ModelChoiceField`): nothing narrows its
   queryset, as ADR 042 refuses one in a form held as state; a field that
   offers request-scoped choices is a child form's (ADR 049). A file field: a
   file is uploaded, not held. A password field whose widget never renders its
   value: it is never signed or sent back.

6. **A field inside a form is unchanged.** Its value stays raw until the form
   cleans it. The field-as-attribute behaviour is the attribute's serializer,
   chosen where the attribute is collected, and the form's fields keep
   theirs.

## Security

- The value is loaded only through the field, so it is cleaned before
  application code reads it; the token signs the prepared value, and
  restoring it cleans it again.
- Queryset fields are refused (rule 5), so no attribute offers or accepts rows
  outside what a request may see.

## Consequences

- One editable value with a label and choices needs no form class. Profitly's
  `NameSortForm` becomes a `sort` attribute.
- ADR 042's rejected alternative "a single form field as an attribute's type"
  is superseded by this record.
- A form held as state stays for a group of fields validated together, such as
  filters whose `clean()` relates them.
- Two ways now hold one value: a typed attribute, for a value with nothing to
  draw, and a field attribute, for one the browser draws a control for.
- The tests: a field attribute reads its cleaned value and its default; the
  browser and the token carry its prepared value; an update the field refuses
  is refused; a value restored from the token is cleaned; `$fields` on a
  component describes it, and a Spire field include binds it; a queryset,
  file or write-only password field is refused at class definition; a form's
  own fields still hold raw values.
