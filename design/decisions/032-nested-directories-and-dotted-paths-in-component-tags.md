# ADR 032: A Component Tag Names Its Nested Directories, Or Is A Dotted Path

Status: Accepted; implemented on branch

Date: 2026-10-09

Partly supersedes [ADR 014](014-lazy-snake-case-component-discovery.md): a
`components` package is no longer scanned through every package inside it.

## Context

[ADR 014](014-lazy-snake-case-component-discovery.md) reads a tag as a directory
and a class name, and scans the `components` package that is a child of that
directory "through its own namespace and every submodule". The scan was
recursive, so a class in `app/components/cards/fancy.py` was stamped as
`app/fancy`, and the `cards` directory appeared nowhere in the tag.

That had three costs:

- **A nested directory was not a namespace.** Two directories inside one
  `components` package that each defined `FancyComponent` resolved to whichever
  the walk reached first, with no error.
- **A nested directory without an `__init__.py` was skipped silently.** The walk
  only enters regular packages, and the resulting error named the `components`
  package, not the directory it had passed over.
- **The tag did not say where the class was.** [ADR 027](027-component-lookup-like-templates.md)
  makes component lookup work the way template lookup does, and a template's
  name includes every directory under the template root.

Separately, a tag could only be a path. A component outside any `components`
module, or one a project wanted to name without relying on the lookup, could
not be stamped, although Glue already imports a component by its
`module.qualname` whenever it reconstructs one from a signed `component_id`.

## Decision

**A path tag names every directory between the `components` package and the
class.** The segments before the class name are a directory that holds a
`components` module or package, then the directories inside that package:

```django
{% glue_component 'app/cards/fancy' %}
```

This tag has two readings: the `components` module of `app/cards`, and the
`cards` directory inside `app/components`. A tag with more segments has one
reading for each place the `components` package could sit. Every reading is
looked up, each the way ADR 027 describes: under each `DIRS` entry, then inside
the installed apps, with the first location that defines the class winning.

**A tag that two readings resolve to different classes is ambiguous and fails**
with `GlueComponentRegistrationError`, naming both classes. The two readings
resolving to one class, because one module re-exports it from the other, is not
ambiguous.

**A reading's package is scanned through its own namespace and its direct
modules only.** The file a class lives in still does not matter. A package
inside it is not searched, because its name is part of the tag. The nested
package is imported by name, so it needs no `__init__.py`.

**A tag may instead be the class's dotted path**, its `module.qualname`:

```django
{% glue_component 'app.components.cards.fancy.FancyComponent' %}
```

It is resolved by the lookup reconstruction already uses for the signed
`component_id`, and that lookup now refuses a name that is not a `Component`
subclass. A dotted path is not searched for in `DIRS` or the installed apps.

## Consequences

- A component in a nested directory must be stamped with that directory in its
  tag, or by its dotted path. A project that relied on the recursive scan
  changes those tags; no project in the Stratus workspace did.
- A class can still move between files without its tag changing. It can no
  longer move between directories without its tag changing.
- A `components/__init__.py` that imports a class from a nested directory keeps
  the short tag working, because the package's own namespace is scanned. That
  is an explicit choice in the project's code, as any re-export is.
- Resolving a tag looks up every reading instead of stopping at the first
  class found, so that an ambiguity is reported instead of settled by search
  order. A tag is resolved once per process and then cached, and a reading
  whose directory does not exist imports nothing.
- A project cannot override a component stamped by its dotted path, since the
  path names one class. Override by tag path is unchanged.
- A dotted path can import any module on `sys.path`, not only one inside an
  installed app. ADR 027 rejected that as a fallback for path tags, where a
  tag could reach a module its author did not name. A dotted path names the
  module outright, and tags are written in server templates, never supplied by
  a client.

## Rejected Alternatives

- **Try the deepest directory first and take the first reading that
  resolves.** Every existing tag keeps its meaning with no extra lookups, but a
  tag with two readings is settled silently by search order, which is the
  failure the recursive scan already had.
- **Keep the recursive scan and fail when two nested directories define the
  same class name.** It removes the silent collision but not the missing
  namespace: class names would still have to be unique across a whole
  `components` package.
- **Reach nested components by dotted path only.** One mechanism instead of
  two, but a project that organizes its components in directories would write
  every tag as a full import path.
- **Make the module's file name part of the tag as well.** The tag would mirror
  the import path exactly, but every existing tag would change
  (`banking/transaction_row` would become
  `banking/transaction_row_component/transaction_row`), and ADR 014's freedom to
  move a class between files would be lost for no gain in clarity.
