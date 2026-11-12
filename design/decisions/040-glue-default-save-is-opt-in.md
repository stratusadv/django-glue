# ADR 040: Glue's Default Save Is Opt-In

Status: Proposed

Date: 2026-11-12

## Context

`FormGlue` declares `save()` on itself, so every glued form offers it to the
browser: `save` is listed under `callables` in the form's `static_data`, and a
call to it binds the form, validates it and, when the form has a `save()`,
runs it. For a `ModelForm` that is Django's `BaseModelForm.save()`:
`instance.save()` followed by the many-to-many fields. `FormSetGlue` offers a
`save()` that does the same for each row. Nothing in that path knows about the
application's own write path.

Applications built on Glue usually write through a path of their own, and the
default save sits beside it as a second way in:

- **A form whose model is saved through a service.** Django Spire's convention
  is that a model is saved through `obj.services.save_model_obj(...)`, and a
  Spire form declares its own `save_model_obj` callable that does so. The
  default save skips the services. In Profitly's Chart of Accounts (PROF-23),
  the browser is sent `save` in `AccountForm`'s callables, and calling it
  creates an account through `ModelForm.save()`, outside `save_model_obj`.
- **A form that only feeds a component's action (ADR 034).** In Profitly's
  journal entries (PROF-31), a header form and a formset of line forms are
  children of one component, whose action validates both and posts the entry
  through the ledger's one post routine, which checks the balance, numbers the
  entry and stamps who posted it. Neither form holds a whole entry, so neither
  form's own save can be that routine, and a browser call to it would bypass
  every rule of the ledger.
- **A plain form.** A `forms.Form` has no `save()`, so the default save
  validates, does nothing, and answers `valid: true` as if it had saved.

The components guide's advice is to "override `save()` on the form class to do
nothing". The browser is still offered `save`, a call to it answers as if it
saved, and each application writes the override again. It also pushes
applications away from `ModelForm`: Profitly wrote its journal forms as plain
forms that copy the model's `max_length`, `max_digits` and `decimal_places`, so
that no model form's save would be exposed, and the copies can drift from the
model.

Calling the default save from the browser is a real feature, but a rare one.
Glue's test project does it on five pages (`fight/page/schedule_page.html`,
`fight/page/list_page.html`, `gorilla/component/fights_editor.html`,
`gorilla/page/skill_formset_page.html`, and the form-proxy modal
`gorilla/component/gorilla_form_modal.html` on the gorilla list page), through
four forms: `FightForm`, `GorillaForm`, `FightNameForm` and `SkillForm`.
Django Spire, the Stratus portal and Profitly do it nowhere; they save through
declared callables.

## Decision

Glue offers a form's default save only to a model form that asks for it, with
`glue_default_save = True` in its `Meta`.

1. **The form's `Meta` is the declaration.** A `ModelForm` opts in beside its
   other per-form choices:

   ```python
   class FightScheduleForm(forms.ModelForm):
       class Meta:
           model = Fight
           fields = ('venue', 'scheduled_for')
           glue_default_save = True
   ```

   Django reads only the `Meta` options it knows and ignores this one, so Glue
   reads it from the form class's `Meta` itself. It is not copied to
   `form._meta`. It is inherited as `Meta`'s other options are: a subclass that
   writes `class Meta(ParentForm.Meta)` keeps it, and one that writes a fresh
   `class Meta` does not.
2. **Without it, `FormGlue` does not offer `save`.** When the wrapped form's
   `Meta` does not set `glue_default_save = True`, `FormGlue` leaves `save` out
   of the attributes it collects for that object
   (`BaseGlue._collect_attributes()`). It is not in `static_data`'s
   `callables`, the client builds no `save()` for it, and a hand-made call to
   `save` is refused as an unknown attribute, as for any name the object does
   not declare. `validate()`, field edits, `foreign_key_choices()` and the
   form's own declared callables are unchanged.
3. **`FormSetGlue` follows its row form class.** A formset offers its own
   `save` only when its `form_class` sets `glue_default_save = True`, and its
   rows, which are `FormGlue` objects, follow rule 2. `append`, `pop` and
   `validate` are unchanged.
4. **Only a form with a `save()` may opt in.** A form whose class sets
   `glue_default_save = True` but has no `save()`, such as a plain
   `forms.Form`, is refused with `ImproperlyConfigured` when it is glued, so a
   misunderstanding is reported rather than ignored. A plain form therefore
   never offers `save`.
5. **The option governs only what Glue offers the browser.** The form's own
   `save()` is unchanged, and server code may still call it. `ModelGlue` is not
   affected: its `save()` writes the instance directly, never through a form,
   and stays governed by its access and its editable fields.
6. **Nothing is signed.** Whether `save` is offered is derived from the form
   class each time the object is built, and the form class is already in the
   identity, so the token gains no content.

## Consequences

- No glued form is a way into the database unless its author says so. A form
  that saves through a service or feeds a component's action needs no
  configuration to be safe, and `AccountForm`'s side path closes when Profitly
  upgrades.
- An application can use a `ModelForm` for its field definitions and
  validation while its own action or service stays the only write path. The
  form's fields, labels, `max_length` and decimal places come from the model
  and cannot drift from it.
- **This is a breaking change.** A page that calls a glued form's or formset's
  `save()` from the browser must add `glue_default_save = True` to the form's
  `Meta`. The test project's four forms opt in with this change, as do the two
  test forms whose tests save through Glue (`TestModelForm` and
  `DisabledNameGorillaForm`). The changelog states it, and the release's
  version must signal it.
- The components guide replaces "override `save()` to do nothing" with: the
  default save is off unless the form opts in.
- Plain forms stop answering a `save` call with `valid: true` while saving
  nothing.
- The tests per family: without the option, a form, a formset and a row each
  omit `save` from `callables` and refuse a call to it; with it, each offers
  and runs `save` as before; a form with no `save()` that opts in is refused;
  every other attribute behaves as before.

## Rejected Alternatives

- **Default save on, with `glue_default_save = False` to turn it off.** It
  keeps existing pages working, but a form is a way in until someone remembers
  to close it, which is how `AccountForm` came to expose one. Few pages call the
  default save from the browser, so opting in costs little.
- **A `ModelForm` subclass, such as `ValidateOnlyModelForm`.** Its name would
  describe the whole form, but the form may still declare callables of its own
  that save, as Spire forms do with `save_model_obj`. Only the default save is
  in question.
- **A mixin on the form.** It works only when listed before `ModelForm` in the
  bases; written the other way round, `ModelForm.save()` wins with no error or
  warning.
- **A `savable=` argument on `Glue.form()` and `Glue.FormSet`.** It would have
  to be repeated wherever a form is glued and threaded through a formset to its
  rows, and in every case found the choice belongs to the form. ADR 036 made
  the same choice for write-only fields: the form's widget, not a
  `Glue.form()` argument, is the declaration.
- **A general argument naming the callables an object exposes.** Only `save`
  needs withholding. Each family declares different callables, so the
  argument's valid values would differ by family, and every call would pass two
  gates, the access cascade and the list.
- **A new access level for editing without saving.** The access levels form a
  cascade in which each grants those below it; "may edit but not save" is not a
  step on it.
- **Implementing a form's `save()` to call the application's write path.** It
  fits a form whose data is a whole model instance, but not one that holds only
  part of what the write path needs, such as one line of a journal entry.
