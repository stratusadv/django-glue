# ADR 020: New Draft Forms Use Admitted Initial State

Status: Accepted; implemented on branch

Date: 2026-09-28

## Context

`QuerySetGlue.new(initial)` admits only keys in the queryset's signed editable
projection and applies them to an unsaved `ModelGlue` draft. A configured
`ModelForm` is a child of that draft. The row builder previously bound its
children before applying `initial`, so the form was constructed from a blank
model and kept blank initial values. Applying the draft later did not replace
the already bound form child. A portal agreement client contact created with
`new({agreement_id: ...})` therefore had a signed form whose required
`agreement` value was `null` and could not save.

## Decision

The row builder accepts the already admitted `initial` for a new draft. It
applies that state to the model before binding children, rebuilds each
configured form from the updated instance, and copies admitted values into
the corresponding form initial fields. A raw relation identity such as
`agreement_id` maps to the form field `agreement`; an unsaved many-to-many
value stays in the draft overlay and maps to its form field as well.

This changes no public call shape. `new(initial)` still requires `ADD` and
rejects every key outside the signed editable projection. Form initial values
are signed in the introduced form's policy. Form validation and application
authorization still run on later calls. Applications remain responsible for
domain rules between admitted fields, such as requiring a contact to belong
to the agreement's partner.

## Consequences

- A form on a new queryset draft starts with the same admitted values as its
  model, including scalar fields and raw relation identities.
- Child addresses are bound after the draft state is applied, so the form
  child introduced in the response has the correct signed initial values.
- Regression coverage is in `test_add_creation.py`; the portal agreement
  detail browser tests cover the foreign-key create flow through Save.
