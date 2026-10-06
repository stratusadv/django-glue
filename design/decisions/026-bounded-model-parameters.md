# ADR 026: Bounded Model Parameters

Status: Accepted; implemented on branch

Date: 2026-09-29

## Context

[ADR 021](021-component-parameter-initializers.md) declares a model parameter by
decorating an initializer whose return annotation names one model class. The token
signs only the row's key, and the model comes from the declaration, so a token
cannot redirect a parameter to another model.

That rule leaves no way to declare a parameter whose row may belong to any of
several models. The driving case is django-spire's comments. `CommentModelMixin`
is an abstract model that any host model inherits, and each `Comment` points at its
host through a generic relation. One comments component should serve every host: a
task, a sales order, an inventory record. Its host parameter cannot name a single
model, because the host's model varies by page.

Without a model parameter, the component falls back to the pattern ADR 021 replaced,
widened to carry the model as well as the key:

```python
class CommentsComponent(Glue.Component):
    content_type_id: int = Glue.ComponentParameter()
    object_pk: int = Glue.ComponentParameter()

    @cached_property
    def host(self):
        model = ContentType.objects.get_for_id(self.content_type_id).model_class()
        return model._default_manager.get(pk=self.object_pk)
```

That brings back both costs ADR 021 names. The parent already has the host and
cannot hand it over, so the host is loaded again, and the key, the model, and the
loading property are spread across three declarations. It adds costs of its own:

- A `ContentType` id is a database row id. It differs between databases, so it
  cannot appear in fixtures or test expectations as a stable value.
- The component depends on `django.contrib.contenttypes` only to name a model.
- Nothing states which models the component accepts. Any content type the server
  signs resolves.

## Decision

**A model parameter's initializer may take the model class as well as the key.**
The return annotation is then an upper bound, not the one model: the parameter
accepts a row of any concrete model that subclasses it.

```python
class CommentsComponent(Glue.Component):
    template = 'django_spire/comment/component/comments.html'

    @Glue.ComponentParameter
    def host(self, model: type[CommentModelMixin], pk: int) -> CommentModelMixin:
        return model._default_manager.get(pk=pk)
```

A parameter whose initializer takes `(self, pk)` is a **concrete** model parameter,
unchanged from ADR 021. One whose initializer takes `(self, model, pk)` is a
**bounded** model parameter.

**Declaration rules.**

- The initializer's arity chooses the form. Any other signature raises
  `GlueComponentParameterError` at class definition.
- A bounded parameter's return annotation may be any model class: an abstract
  model, a concrete parent, or `Model` itself when the parameter really accepts any
  model.
- A concrete parameter's return annotation must be a concrete model, because its
  key is converted through that model's primary key field. An abstract model or
  `Model` itself raises `GlueComponentParameterError` at class definition, naming
  the bounded form.
- Every other ADR 021 rule applies to both forms: the method name is the parameter
  name, the initializer is never client-callable, and the parameter cannot be
  editable.

**The token signs the model's label with the key.** A bounded parameter's value in
`target.parameters` is `{'model': '<app_label>.<model_name>', 'pk': <key>}`, using
the model's lowercase label and the key signed as ADR 021 signs it. A concrete
parameter's value stays the bare key.

**The declaration still bounds the model.** When a signed value is decoded, its label
must name an installed, non-abstract model that subclasses the declared bound.
Otherwise the parameter raises `GlueComponentParameterError`
(`invalid_component_parameter`) before the initializer runs. The token is signed,
so a client cannot choose the label. The check covers a server that signs a value by
hand, and a token that outlives a model's rename or removal. The label and the
bound together keep ADR 021's guarantee: a token cannot redirect a parameter to a
model its declaration does not accept.

**Construction accepts a row or the signed value.**

- A saved instance of a concrete subclass of the bound is used as supplied, as in
  ADR 021.
- The signed mapping, `{'model': ..., 'pk': ...}`, is decoded as above and its key
  resolved through the initializer. Reconstruction supplies this form.
- A bare key is rejected, because it does not say which model it belongs to. So is
  any other value.

**Reconstruction passes the model and the key.** Every later request calls
`initializer(self, model, pk)`, where `model` is the class the label names. A
`DoesNotExist` from that model fails the address with `model_instance_not_found`,
as in ADR 021. The initializer must return an instance of `model`.

**Everything else follows ADR 021.** Resolution is lazy and happens at most once per
object, server code may retarget the parameter by assigning an instance or the signed
mapping, and `DJANGO_GLUE_VERIFY_MODEL_PARAMETERS` verifies a supplied instance by
calling the initializer with that instance's own model and key.

## Consequences

- One component class can represent a row of any model under a bound. A host that
  already has the row passes it and the component issues no query for it, as ADR
  021 provides for concrete parameters.
- The bound documents and enforces which models a component accepts. A narrow bound
  such as an abstract mixin is the expected use; `Model` itself is available but
  says nothing about the rows the component can handle.
- Signed values name models by label, so they are stable across databases and
  readable in tests. Glue does not depend on `django.contrib.contenttypes`.
- Existing concrete parameters and their tokens are unchanged.
- A bounded initializer usually loads through `model._default_manager`. Scope that
  every accepted model shares belongs in the bound, for example as a manager or
  queryset method the abstract model declares, so the initializer applies it the
  same way for every model.
- `ModelParameter` has two forms. The concrete form's one-argument initializer, bare
  key, and key conversion are unchanged. The bounded form adds the label, the bound
  check, and the two-argument call.

## Rejected Alternatives

- **Scalar `content_type_id` and key parameters with a loading property.** This is
  the context's example. It restores the duplication and boilerplate ADR 021
  removed, and adds an id that differs between databases, a dependency on
  `contenttypes`, and no statement of which models are accepted.
- **Signing a `ContentType` id inside the model parameter.** It keeps the one
  declaration but signs a database-specific id and costs a lookup to name a model
  whose label the instance already carries.
- **One `(self, key)` initializer signature for every model parameter, with the key
  carrying `.model` and `.pk`.** It is uniform, but it changes every existing
  initializer and adds a model the concrete form already knows from its annotation.
- **Inferring the bounded form from an abstract return annotation, keeping
  `(self, pk)`.** The initializer would then need the model without being given it.
  It could not load the row without reading a side channel.
- **Resolving a bounded parameter through the model's default manager, with no
  initializer.** ADR 021 rejects decoding through the default manager because it
  resolves rows outside the consumer's scope. The same holds here.
