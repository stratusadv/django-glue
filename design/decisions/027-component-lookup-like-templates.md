# ADR 027: Components Are Found the Way Templates Are

Status: Accepted; implemented on branch

Date: 2026-09-29

## Context

[ADR 014](014-lazy-snake-case-component-discovery.md) resolves a component tag to
a `components` module under one directory, the components root: `settings.BASE_DIR`,
or `DJANGO_GLUE_COMPONENTS_ROOT` when set. The tag
`app/time_tracker/time_entry_day` imports the `components` package at
`<root>/app/time_tracker`.

That covers a project's own components and nothing else. A reusable library cannot
ship components a project stamps by tag, because the library is installed in
site-packages, outside the project's root. django-spire is the driving case: its
comments component lives in `django_spire.comment.components`, and
`{% glue_component 'django_spire/comment/comments' %}` resolves in spire's own test
project only because that project's `BASE_DIR` happens to be the spire repository.
In a consumer project the tag fails with "not under a sys.path entry". One portal
also narrows its root to `BASE_DIR / 'app'`, which would hide such a component
even if the library were vendored under the project.

Django solved the same problem for templates. `TEMPLATES` has two lookup
mechanisms: `DIRS`, an explicit list of project locations searched first, and
`APP_DIRS`, which searches inside every installed app. A library's templates work
in any project with no configuration, and a project overrides one by placing its
own at the same path in a `DIRS` location.

Glue has only the `DIRS` half, limited to one directory, under a name that does not
suggest the correspondence. Glue has few consumers today, so the setting can be
reshaped now at the lowest cost it will ever have.

## Decision

**Component lookup is configured by one setting shaped like `TEMPLATES`:**

```python
DJANGO_GLUE_COMPONENTS = {
    'DIRS': [BASE_DIR / 'app'],
    'APP_DIRS': True,
}
```

- `DIRS` is a list of directories, searched in order. It defaults to
  `[settings.BASE_DIR]`.
- `APP_DIRS` enables lookup inside installed apps. It defaults to `True`.
- Either key may be omitted, and so may the whole setting, so a project that
  configured nothing resolves exactly as it did under ADR 014.

**A tag is resolved against each location in order, and the first location whose
`components` module defines the class wins.**

1. For each entry in `DIRS`, the tag's directory is a path under that entry, as ADR
   014 describes for its single root. A location with no `components` module or
   package there is skipped. A location that has one Glue cannot import, because
   no `sys.path` entry contains it, fails resolution at once with
   `GlueComponentRegistrationError` naming the entry. That is a misconfigured
   entry, not a missing component, and skipping it would let a later location
   answer in its place without anyone noticing.
2. If `APP_DIRS` is on, the tag's directory is read as a dotted package path:
   `django_spire/comment` is `django_spire.comment`. That package is searched only
   when it is an installed app or lies inside one. Its `components` module is
   imported by that name.
3. If no location defines the class, resolution fails with
   `GlueComponentRegistrationError`, naming every module it searched.

A `components` module found at a location is scanned exactly as ADR 014 describes.
If it does not define the class, the search moves to the next location, as Django
moves to the next template directory when a file is missing. A project therefore
overrides a library's component by defining the same class name at the same tag
path under one of its `DIRS`.

**`DJANGO_GLUE_COMPONENTS_ROOT` is removed.** A project that still sets it fails the
system check `django_glue.E004`, whose hint gives the replacement,
`DJANGO_GLUE_COMPONENTS = {'DIRS': [<root>]}`. A malformed `DJANGO_GLUE_COMPONENTS`
(not a mapping, an unknown key, `DIRS` not a list or tuple, or `APP_DIRS` not a
boolean) fails `django_glue.E005`.

**Resolution stays lazy.** Nothing is imported at startup. A tag's first use imports
only the `components` modules at the locations its own path names, and the result is
memoized as before.

## Consequences

- A library ships components the same way it ships templates. A project installs
  the library's apps and stamps the components by their package path, with no
  setting.
- A project can override a library's component, as it overrides a library's
  template.
- `APP_DIRS` bounds what a tag can import to packages the project already installed
  as apps. Tags are written in server templates, never supplied by a client, so the
  bound guards against mistakes rather than attacks.
- A project that set `DJANGO_GLUE_COMPONENTS_ROOT` must rename it. The system check
  makes the change fail loudly at startup, with the replacement in its hint, instead
  of silently changing where components are found.
- A tag whose class is missing from an earlier location now keeps searching. A typo
  in a class name reports every module searched, not only the first.

## Rejected Alternatives

- **An import-path fallback for any importable package.** It needs no setting, but a
  tag could then import any module on `sys.path`. Limiting the fallback to installed
  apps keeps Django's rule that code a project did not install is never searched.
- **A setting listing extra packages to search.** It is explicit, but every consumer
  of a library must add the library to the list, and a missing entry fails only when
  the tag first renders. Installed apps already carry that opt-in.
- **Keeping `DJANGO_GLUE_COMPONENTS_ROOT` and adding app lookup without a setting.**
  It avoids a rename now, but leaves two lookup mechanisms configured by one setting
  named for neither, and the rename only gets more expensive as projects adopt Glue.
- **Eager startup discovery of every installed app's components.** ADR 014 rejected
  it for its startup cost, its coupling of components to apps, and its tag
  collisions. `APP_DIRS` keeps lazy resolution and names the package in the tag, so
  two apps' components never share a tag.
- **Separate settings, such as `DJANGO_GLUE_COMPONENT_DIRS` and
  `DJANGO_GLUE_COMPONENT_APP_DIRS`.** One mapping mirrors `TEMPLATES` exactly, which
  is the reason for the change.
