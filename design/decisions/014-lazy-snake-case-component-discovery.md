# ADR 014: Lazy snake_case component discovery by name

Status: Accepted; implemented on branch

Date: 2026-09-25

## Context

`component-system.md` §5 currently treats the component tag as a **derived,
pre-registered** value. A `Component` subclass computes a kebab-case `tag_name`
from its class name at import (`__init_subclass__` strips a trailing `Component`
suffix and kebab-cases the rest), a startup `autodiscover_components()` pass
imports every installed app's `components` module and registers each class by
that tag, and the `{% glue_component %}` tag resolves by looking the tag up in a
registry that must already be populated. Django's startup checks reject two
classes claiming the same tag.

This shape has three costs the component work no longer wants:

- **Eager, app-coupled startup.** Every installed app's `components` package is
  imported at boot, so a project's startup pays for and depends on every
  component it ships, even ones no request renders.
- **The class name drives the address.** The tag is computed from the class, so
  you cannot address a component by a stable path without importing its app,
  and two apps that both name a class `MyCard` collide on a tag at startup.
- **Two naming conventions.** Kebab-case public names and `Component`-suffixed
  class names are coupled by derivation, and the `tag_name` override exists only
  to escape that coupling.

The component work wants the template tag to be the **address**, resolved on
demand, in a shape that reads like the module that would define it.

## Decision

The template tag name is the source of truth. It is a **snake_case** path: an
optional directory prefix, then the component name, separated by slashes:

```django
{% glue_component 'my_custom_card' ... %}                  # <root>/components
{% glue_component 'task/my_custom_card' ... %}             # <root>/task/components
{% glue_component 'app/time_tracker/time_entry_day' ... %} # <root>/app/time_tracker/components
```

The last segment is the component (class) name; the segments before it are a
directory path, and the `components` package is a fixed child of that
directory.

Resolution is **lazy** and happens at first use of the tag (and at
reconstruction), not at startup:

1. Split the path on `/`: the last segment is the snake_case component name,
   the segments before it form a directory path
   (`app/time_tracker/time_entry_day` → directory `app/time_tracker`, leaf
   `time_entry_day`).
2. Derive candidate class names from the leaf by Pascal-casing it, trying the
   `Component`-suffixed form first: `my_custom_card` → `MyCustomCardComponent`,
   then `MyCustomCard`.
3. Import the `components` package that is a child of that directory —
   `<directory>.components` (dotted), or `components` at the root — from the
   components root. The root defaults to the Django project's `settings.BASE_DIR`
   and is overridable via `DJANGO_GLUE_COMPONENTS_ROOT`.
4. Scan that package (its own namespace and every submodule, by class name —
   **the file name is irrelevant**) for a `Component` subclass matching a
   candidate, and return it.

`component_registry` stops being a pre-registered index and becomes a **cache**
populated on demand. `from_tag_name(tag)` resolves lazily as above and caches the
result; `from_identifier(module.qualname)` — the path reconstruction already
takes, from the signed `component_id` at `component.py` — lazily imports the
module and walks the qualname to the class, caching that too. `register()`
(still invoked from `__init_subclass__`) now only *pre-warms* the identifier
cache; it is never a precondition for a tag to resolve.

Consequences that fall out of the decision:

- Startup no longer imports component modules. The `autodiscover_components()`
  pass and the tag-name collision system check are removed — with a
  tag→module address there is no shared tag name left to collide on.
- The `tag_name` ClassVar and its kebab derivation are deleted. The class no
  longer computes its public name; the tag in the template is the name.
  `as_view()` and reconstruction never read `tag_name`, so nothing else changes.
- The tag names the class. `my_custom_card` can only resolve to
  `MyCustomCard(Component)`; the convention is binding, as with
  Django's `app.Model` and Rails' `ActiveRecord` resolution.
- The root must already be importable: the `components` directory has to sit
  under an existing `sys.path` entry. Glue does not modify `sys.path`; it
  derives the module's dotted name from its position relative to the closest
  (deepest) `sys.path` ancestor, so the component keeps the identity the
  project already imports it under, and its `module.qualname` — and therefore
  its signed `component_id` — stays stable for reconstruction.

## Consequences

- A component is found wherever it is defined inside `<root>/<directory>/
  components`, so the class can move between files without changing its tag.
- First render of a tag pays one import pass over that `components` package;
  Python caches the imports, so subsequent renders and all reconstruction are
  cache hits.
- The per-instance address is `{tag}:{canonical}`, so the snake_case path tag
  flows into the signed address. This changes component addresses versus the
  kebab scheme and invalidates any pre-existing component policy tokens. That is
  acceptable on the unreleased `v1.1` branch, where the wire is already
  mid-migration with no compatibility envelope.
- A component must live under a real Python package rooted at the components
  root; a directory such as `task` is an ordinary importable package, not a
  Django app.
- Known limitation: the dotted name comes from the deepest `sys.path` entry
  containing the `components` directory. If a project puts both a directory
  and one of its descendants on `sys.path` (say `BASE_DIR` and `BASE_DIR/app`),
  Glue imports `time_tracker.components` while the project imports
  `app.time_tracker.components`. Python then loads the module twice, each
  component class exists twice, and a stamp and a reconstruction can disagree
  on which class they hold. Keep only one `sys.path` entry above the components
  root. A fix that prefers a module already in `sys.modules` whose file matches
  is possible but not implemented.

## Rejected alternatives

- **Keep startup autodiscovery and the tag registry.** Eager, app-coupled, and
  it preserves the class→tag derivation this ADR removes. The registry survives,
  but only as a lazy cache.
- **A settings list of explicit component modules.** Drops the by-name
  convention — the developer re-declares, per module, what the tag already
  encodes, and a new component needs a settings edit.
- **Import the `components` directory by file path, without a stable dotted
  module name.** Breaks reconstruction: the signed `component_id` is
  `module.qualname`, and a path-loaded module has no stable dotted name for a
  later request to re-import.
- **Keep kebab-case tags and only make discovery lazy.** Solves the eager-import
  cost but keeps the class→tag coupling and the two-convention mismatch the
  component work wants gone.
