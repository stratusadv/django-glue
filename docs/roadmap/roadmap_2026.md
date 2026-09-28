# Reactive system roadmap

The state-model redesign is implemented on `v1.1/base`; consumer migration and
release review remain.
Its implementation phases are internal checkpoints, not separate releases.
The repository's `design/roadmap.md` owns the detailed gates.

The release gate includes the addressed server and client protocol, built-in
Glue families, component stamping and lifecycle, consumer migration, and
green Python, JavaScript, E2E, Django check, and documentation builds.

Later work includes transport status bindings, interval polling, optimized
collection moves, incremental component rendering, reactive component
parameters, and optional queryset preload. Security hardening outside the
state-model release is tracked separately in the design roadmap.
