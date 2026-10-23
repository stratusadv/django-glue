# ADR 037: A Redirecting Call Does Not Re-render Its Component

Status: Accepted

Date: 2026-10-23

## Context

ADR 022 makes a component callable re-render its component in the same
response, and lets `skip_rerender=True` opt out, unless the callable changed a
retained value: then the markup would no longer match the component's state, so
Glue re-renders whatever the callable declared.

A callable that returns `Glue.RedirectResponse` sends the browser to another
page. The client follows the redirect, so the re-rendered HTML is never shown,
and the render is wasted work: a reconstruction, the component's queries and its
template.

It is also wrong when the call changes who the user is. Profitly's sign-up
callable creates an account, calls Django's `login()`, and redirects to the new
company. Logging in changes the session and the user the successor token is
bound to, so the token changes and the retained-value guard forces a re-render
even with `skip_rerender=True`. The re-render reconstructs the component as the
newly logged-in user, and a component that admits only visitors without an
account, through a `user_passes_test` decorator on `is_authorized()` (ADR 033),
refuses it. The sign-up succeeded and its writes committed, but the address
answers `not_authorized`. Accepting an invite as a new user, PROF-18, has the
same shape.

## Decision

**A callable whose response redirects does not re-render its component.** The
redirect overrides the default re-render and the retained-value guard alike: the
browser is leaving the page, so no markup on it needs to match the component's
state.

1. A response redirects when it carries a redirect effect, which
   `Glue.RedirectResponse` sets.
2. The callable's entry is returned as it stands: its result, effects, successor
   token if one was issued, and any objects it introduced. No fresh instance is
   reconstructed and no template renders, so no authorization runs for a
   render.
3. The rule applies to component callables only, like ADR 022. Other Glue
   objects never re-render.

## Consequences

- A redirecting call costs one render less. The prototype's `send_invoice` is
  one such call today.
- A component can guard itself with `is_authorized()` even when its callable
  logs the user in or out, provided the callable redirects, which a call that
  changes who the user is normally does.
- A callable that changes the user without redirecting still re-renders as the
  new user, and its component must admit that user.

## Rejected Alternatives

- **Excluding the token's subject from the retained-value guard.** A login would
  then let `skip_rerender=True` hold, but the callable would have to declare it,
  and a redirect that needs no declaration would still render for nothing.
- **Guarding the URL with a view decorator instead of `is_authorized()`.** It
  works for sign-up, because the logged-out token fails once the session
  changes, but it splits one component's access rule between its URL and its
  class, and the component itself states nothing.
- **Skipping the re-render when the user changed, without a redirect.** The page
  would keep markup rendered for the previous user. A redirect is the signal that
  the markup no longer matters.
