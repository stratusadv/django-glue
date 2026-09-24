# ADR 013: The Policy-Token Lifetime Is 24 Hours From Issuance

Status: Accepted; implemented on branch

Date: 2026-09-22

## Context

`state-model.md` §10's child-reintroduction contract "depends on a known
expiry", and the roadmap's security-hardening list requires one documented
policy-token lifetime before that path is implemented. The code shipped with
`DJANGO_GLUE_PROXY_POLICY_MAX_AGE_SECONDS = 86400` (24 hours) while older
documents also named 10 minutes and 1 hour, so no single choice was
documented.

Three properties frame the choice. First, a policy token is not an
independent bearer credential: every request cross-checks the token's signed
`session_id` against the request's session and re-runs current application
authorization per request and, for relations, per instance. The lifetime
therefore is not a primary security control; it bounds the replay/staleness
window of an already-issued token — the residual property the state model
deliberately accepts (a relation policy issued while the user had access
stays usable until expiry even if the row that introduced it leaves the
collection).

Second, an expired page root has no reintroduction path: an expired root is a
reload, which can discard in-progress root-level editable work held in the
client. A child, by contrast, is repaired by the §10 reintroduction contract
— the client keeps the user's work and receives a fresh token — so child
expiry costs one extra round trip, not lost work.

Third, the token a client holds expires at a fixed point: issuance
(`created_at`) plus the configured lifetime. A successor token with a fresh
issuance is delivered only when the object's retained values change, so an
object whose state never changes does not roll, while an actively edited one
renewes continuously.

## Decision

One documented default: `DJANGO_GLUE_PROXY_POLICY_MAX_AGE_SECONDS = 86400`
(24 hours), fixed from issuance.

Twenty-four hours reads as "a page is live for one working day": a root left
untouched for a full day is a reload, which the spec names the correct
outcome for a page whose session-scoped capability has run out, and a child
issued at the start of a session that is first touched the next morning
expires in the interim — exactly the §10 scenario reintroduction is built for,
repaired automatically.

The value remains a per-deployment setting; this ADR fixes the library
default and its documented semantics, not a ceiling.

## Consequences

- The roadmap item "Choose and document one policy-token lifetime" is closed;
  the A3 reintroduction protocol implements against a known expiry.
- Documentation states the semantics precisely: fixed from issuance,
  successor-issued when retained values change, session-bound and re-authorized
  on every request.
- Deployments with a tighter replay-window requirement lower
  `DJANGO_GLUE_PROXY_POLICY_MAX_AGE_SECONDS`; roots then reload sooner and
  children reintroduce sooner.

## Rejected alternatives

- **10 minutes or 1 hour.** The marginal security gain is small because the
  session cross-check and per-request re-authorization are the primary
  controls, while the cost is concrete: roots have no reintroduction path, so
  an hour (less for ten minutes) of a left-open page ends in a reload that
  discards in-progress root-level edits.
- **No expiry (session-lifetime tokens).** The reintroduction contract needs a
  known expiry to define the stale child, and an unbounded token maximizes the
  accepted replay/staleness residual.
- **Rolling expiry on every interaction.** A no-op call would silently extend
  every token, defeating the bound on the staleness residual and making the
  §10 "untouched child expires" scenario unreachable.
