# ADR 036: Password Inputs Are Write-Only

Status: Accepted

Date: 2026-10-23

## Context

`FormGlue` signs the current value of every editable field into the successor
token's `state_snapshot` (state-model.md §1, §2): the server consumes the draft
on the next request, so the draft is retained state. The token is signed, not
encrypted, and the client decodes it on purpose (§10). For a password field
that is the wrong place. A sign-up form whose call fails validation answers
with a token that carries the plaintext password back to the browser, where it
stays readable for the token's 24 hours (ADR 013), and every later response
re-signs it.

Django settled the same question for HTML forms. `PasswordInput` takes
`render_value`, which defaults to `False`: a re-rendered form never writes the
password back into the page. A form author already states "this value goes up
and never comes back" by choosing that widget, and Glue ignores the statement.

The problem is not one form's. Account sign-up, accepting an invite with a new
password and changing a password are all forms, and a project that builds its
forms with Glue meets it on each of them. Profitly's owner sign-up (PROF-11) is
the first.

## Decision

A `FormGlue` field whose widget is a `PasswordInput` with
`render_value=False` is **write-only**. The browser may send its value; the
server never sends it back.

1. **Django's widget is the declaration.** No new argument marks a field
   write-only. `PasswordInput()` and any subclass with `render_value=False`
   are write-only; `PasswordInput(render_value=True)` opts back into ordinary
   editable state, exactly as it opts back into re-rendering in Django.
   Write-only is decided from the form class's fields each time the form is
   built, so it never needs signing.
2. **The server never emits the value.** A write-only field is left out of
   `state_snapshot` and out of the identity's signed `initial`, and every read
   of its declared attribute (the client-facing property for a field that is
   not editable, the retained draft for one that is) yields nothing. Its
   descriptor in `static_data` stays, with `write_only: true`, and its errors
   still reach `computed_data`, so the field renders, labels and validates as
   any other.
3. **The value still arrives as an update.** Writability is unchanged: the
   field is editable when the editable projection (§9) makes it so, and its
   value enters through the ordinary admitted `updates` channel. The server
   binds it for that one call. With no retained draft, a call that does not
   carry the update binds the field empty, so validation reports it missing.
4. **The client keeps what the user typed.** A write-only path never enters the
   client's canonical state, and a response never patches, replaces or deletes
   its reactive value. Its canonical baseline is therefore always absent, so a
   value the user has typed is sent as an update on every call its record makes
   (including a component call that submits it as a child, ADR 034), and a
   failed submission leaves the field filled in. Clearing it is the
   application's choice, made as for any other client value.
5. **The request is marked sensitive.** A call that admits an update to a
   write-only field adds `objects`, the POST parameter that carries the call's
   entries, to the request's `sensitive_post_parameters`. Django's error
   reports then hide the call body, as `@sensitive_post_parameters` hides a
   password posted to an ordinary view.

`ModelGlue` is unchanged: its fields project model metadata rather than form
widgets, and Django's `User.password` holds a hash. A formset's rows are
`FormGlue` objects and follow these rules.

## Consequences

- A password field in a Glue form no longer leaves the server. Tokens, response
  entries and logged error reports carry no password; only the call that
  submits it does, as a form post would.
- A form that holds a password needs no extra configuration, and an existing
  form gains the protection without a change.
- The client sends a typed password with every call its record makes, not only
  on submit. The value travels where it would in any form post, but more often.
- A field that used `PasswordInput` for a value the application meant to show
  again must say `render_value=True`, as it must in Django.
- The wire gains one descriptor flag, `write_only`, and the client one rule. The
  server's write-only set is derived, never signed, so there is no new token
  content to verify.

## Rejected Alternatives

- **A `write_only=` or `sensitive=` argument on `Glue.form()`.** It restates
  what the widget already says, in a second place a form author can forget,
  and a formset's or a model's embedded forms would each need it threaded
  through.
- **Encrypting `state_snapshot`.** The token is readable by design (§10), and
  encrypting it would still hold the password for the token's lifetime, re-sign
  it on every response and add key management.
- **Holding the draft in the component session (ADR 031).** The password would
  rest in the session store, keyed per component class, and a `Glue.form()`
  built outside a component has no component session.
- **Clearing the field after every response, as a Django re-render does.** Any
  call on the record, such as a related-choice search or a component call that
  submits the form as a child, would wipe what the user had typed.
- **Building password forms as plain Django views.** It works for one form, but
  every later password form meets the same problem, and the project loses the
  one way it builds forms.
