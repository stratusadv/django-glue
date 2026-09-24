# ADR 001: Bundle Alpine with Django Glue

Status: Accepted and implemented on the feature branch

Date: 2026-09-10

## Context

Glue's client behavior and component design depend on Alpine reactivity and DOM
morphing. Allowing consuming projects to supply arbitrary Alpine core and morph
versions creates lifecycle ambiguity, compatibility risk, and a longer install.

## Decision

Glue bundles one pinned Alpine core and matching morph plugin, exposes that
runtime as `window.Alpine`, and owns startup. Consuming projects remove their
separate Alpine core and morph scripts. Optional Alpine plugins remain
project-owned and register against Glue's runtime before startup.

All direct Alpine integration remains behind Glue's Alpine adapter module. The
public Glue client remains organized around Glue objects rather than exposing
Alpine internals as its API.

## Consequences

- Glue can guarantee compatible reactive and morph behavior.
- Installation becomes shorter and deterministic.
- Loading or replacing a second Alpine core is an installation error.
- Alpine upgrades become Glue release decisions and require compatibility
  testing against consuming projects.
- **A consuming project has no route to an Alpine patch faster than a Glue
  release, and no supported way to substitute a build.** This is accepted rather
  than overlooked: the spike showed that an arbitrary morph implementation
  desynchronizes silently from Alpine state, and a substitutable core reopens
  exactly the compatibility ambiguity this decision closes. The mitigation is
  release responsiveness, not a configuration switch. Glue must be able to ship
  an Alpine bump as a patch release without other changes riding along.
- **The CSP commitment in `roadmap.md` requires a second bundle.** A
  CSP-compatible Alpine replaces the evaluator, which is a build-time choice
  rather than a runtime flag. Bundling and the CSP goal are therefore in tension,
  and the resolution is two published bundles from one pinned Alpine version —
  the default and a CSP variant — selected at install time. `client_js/src/alpine.js`
  is the only module that touches Alpine, so it is also the only module that
  varies between them; that module is being written on this branch and should be
  structured for the split now rather than refactored for it later.

## Rejected alternatives

- Continue requiring projects to install matching Alpine and morph versions.
- Preserve a framework-agnostic morph seam; the spike showed that generic DOM
  morphing can silently desynchronize Alpine state.
