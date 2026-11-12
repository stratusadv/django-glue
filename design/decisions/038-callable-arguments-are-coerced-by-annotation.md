# ADR 038: Callable Arguments Are Coerced by Their Annotations

Status: Accepted

Date: 2026-10-23

## Context

A callable's signed capability lists the arguments the client may supply, and
Glue refuses any other name. It checks nothing about the values: an admitted
argument reaches the callable exactly as the browser sent it. An argument
annotated `int` receives `"5"`, `[1, 2]`, `{"$gt": 0}` or `null`, so the
annotation reads as a guarantee the server does not keep.

A call that leaves out an argument with no default fails worse. Resolving the
arguments raises a plain `ValueError`, which is not a `GlueError`, so the
resolver does not turn it into an error entry for that address. The whole
request fails with a server error, and every other entry in the batch fails with
it, against the independence rule of `state-model.md` §10.

Showcase works around both. Every one of its 150 component callable arguments
is declared `object = None` and checked by hand at the top of the method, and a
test fails the build when a callable argument has no default. The portal
annotates its arguments and trusts them.

The design already places this check. Protocol admission covers "payload shape,
decoding" and argument interiors, and an unkeyed argument is "validated by its
declared serializer" (`state-model.md` §"Editable updates"). Glue already has
that serializer: `glue_serializer_registry` coerces component parameters,
editable updates and field values against their declared types. Callable
arguments are the one inbound value that skips it.

## Decision

**Glue coerces each admitted callable argument through the serializer registry
against its annotation before the callable runs.**

1. **The annotation is the declaration.** An argument annotated with a type is
   coerced to it. An unannotated argument, or one annotated `object` or `Any`,
   reaches the callable unchanged.
2. **Coercion is lenient by default**, as the registry already is for updates
   and parameters: `"5"` becomes `5` for an `int`, while `"5.5"`, `"abc"`, a
   list or a dict is refused. Values taken from the DOM, such as a `<select>`
   bound with `x-model`, arrive as strings and still work. An argument opts into
   strict coercion, or adds constraints, through `Annotated`, for example
   `Annotated[int, Strict(), Field(ge=1)]`.
3. **A refused value is an error for that address.** It raises
   `GlueRequestError` with `invalid_kwargs`, "Argument value could not be
   coerced.", and details naming the attribute and the argument, never the
   value. This mirrors the refusal of an update (`invalid_updates`). A missing
   argument with no default raises the same code. Other entries in the batch
   proceed.
4. **Coercion follows authorization.** Arguments are coerced when the callable
   is invoked, after the name allow-list and `is_authorized()`. A caller who may
   not make the call learns nothing about its argument shapes.
5. **An annotation Glue cannot use is a declaration error.** Each
   client-supplied argument's annotation is resolved on its own, with its
   `Annotated` metadata, when the class's attributes are collected, and the
   registry prepares its serializer then. An annotation that cannot be
   resolved, such as a type imported only under `TYPE_CHECKING`, or one no
   handler can serialize, raises `TypeError` naming the callable and the
   argument. It never degrades to an unchecked argument. Injected arguments are
   not resolved, so an injected `request: HttpRequest` may stay a
   type-checking-only import.
6. **A handler decides for its own types.** `GlueSerializerHandler.prepare()`
   checks a type before any value arrives. The annotation handler builds its
   cached adapter there. A project's handler for its own type is consulted
   first, as it is for coercion.
7. **The wire does not change.** `static_data` keeps listing argument names
   only. The parameter descriptions in the spec's static-data example (type,
   required, default) stay unimplemented: coercion needs none of them, and
   nothing on the client reads them.

## Consequences

- An argument's annotation is enforced: `def delete(self, pk: int)` receives an
  `int` or does not run.
- A project that checks argument types by hand can declare them instead. A
  project-specific rule, such as refusing a NUL character, can ride on the
  annotation as a Pydantic validator in `Annotated`.
- Code that worked against unchecked arguments can change. A value its
  annotation refuses now fails the call. A value the annotation converts arrives
  converted, so `"false"` for a `bool` is `False`, not a truthy string. A class
  whose argument annotation cannot be resolved at runtime now fails when its
  attributes are collected.
- A `Glue.function` target's own arguments are not covered: the target is
  reached through `FunctionGlue.execute(kwargs)`, whose one argument is a dict.

## Rejected Alternatives

- **Strict coercion by default.** It refuses the strings that form controls
  produce, so every select-driven call would need an explicit conversion in its
  template. Strict coercion stays one `Annotated` away for the arguments that
  want it.
- **Skipping an argument whose annotation cannot be resolved.** The annotation
  would read as checked while nothing checks it, which is the gap this record
  closes.
- **Warning and skipping.** It leaves enforcement to whether a project turns
  the warning into an error, for a check about untrusted input.
- **A Pydantic layer of its own for arguments.** The registry already coerces
  every other inbound value and lets projects add handlers. A second mechanism
  would let arguments and updates of the same type disagree.
- **Coercing before authorization.** It would answer an unauthorized caller
  with the shape of the arguments it got wrong.
