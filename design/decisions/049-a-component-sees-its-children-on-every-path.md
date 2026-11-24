# ADR 049: A Component Sees Its Children On Every Path

Status: Proposed

Date: 2026-11-22

## Context

A child Glue object (`@Glue.child`, ADR 034) is an island: it has its own signed
token, access and lifecycle, and its owner's token holds only the address of
each child, never its state (component-system §7, ADRs 002 and 004). A call
carries each declared child the user may change, with its unsaved values, and
the owner reads that submission when it reads the child.

ADR 042 found that a filter can't be a child form, because the owner sees a
child's values only inside a call that submitted it: "a refresh carries no
children, and outside a submission each read of a child runs its initializer
again." It rejected changing that ("a child form read outside calls") as three
changes to how components see children, and held filters as a form in the
component's own state instead.

A form held as state is built from its values alone, so it can't take the
request's context: its class's `__init__` may require no argument, and a field
over a queryset is refused. A filter therefore can't offer a `ModelChoiceField`
narrowed to what the request may see, such as Profitly's account filter
narrowed to the user's company, or the customer, vendor and product filters
that follow it. Child forms already do all of this: constructor arguments
signed and replayed (ADR 041), fields narrowed with `Glue.choices`, Django's
validation against the narrowed queryset, and `foreign_key_choices` to search
it.

A spike against the current code measured which paths an owner sees a child's
values on, with a child filter form declared at `CHANGE` under a component at
`VIEW`:

| Path | The owner reads |
| --- | --- |
| The first render | the initializer's child: nothing has been typed yet |
| A call, such as a scroll's `load_items` | the submitted values |
| A `render` call, how the client fetches a component's HTML | the submitted values |
| Two reads in one call with a submission | the same object |
| The re-render after a call (ADR 022) | **the initializer's child** |
| A refresh (`$refresh()`, a request with no attribute) | **the initializer's child** |
| Two reads in one request without a submission | **two objects, the initializer run twice** |

The child kept its own access (`CHANGE`) under its `VIEW` owner (ADR 028), so
the client submits it for a user who may only view the list.

On those three paths the owner recreates a child that already exists instead of
reading it. That treats the island's state as the owner's, derived afresh on
each request, which is what an island rules out. In the client a parent's
render already keeps each mounted child's newer draft (ADRs 004 and 025); on
the server the owner replaced it with its initializer's child. The gap is
three places where children aren't carried, not a change to how components see
children:

- The re-render after a call is rendered by a fresh component rebuilt from the
  successor token (`Component._rerendered`), with a request context that
  carries no child submissions.
- The client sends no children with a refresh (`GlueComponentProxy._requestFields`
  returns before them when the attribute is `None`), and the server reads
  submissions only inside a call.
- A child read with no submission is built by its initializer on every read.

No application code relies on any of them. In Profitly, django-spire and the
Stratus portal, an owner reads its children only in calls that consume the
submission: those calls redirect on success, which does not re-render
(ADR 037), and on failure the re-render already leaves each mounted child's
values and errors in the client (ADR 025). No template or derived value of an
owner reads a child on the server.

## Decision

A child, once it exists, persists as an island: its owner reads it as it
currently is, through the child's own token and the user's changes, and never
recreates it. An initializer creates a child: it runs where the child doesn't
exist yet, and once per request at most. So a component sees each child the
user has changed on every path that renders or derives from it.

1. **The re-render after a call carries the call's children.** The render that
   replaces a call's output (ADR 022) is given the call's child submissions,
   with each child the call read replaced by its successor: its new token and
   no further changes. The re-render therefore reads each child as the call
   left it. A child the call didn't read is carried as it was submitted.

2. **A refresh carries children.** The client sends a refresh the same child
   submissions it sends a call: each child declared with `Glue.child` whose
   slot submits with its owner and whose access is above `VIEW`. The server
   reads them on a refresh as it does in a call: checked when the owner reads
   the child, and only then.

3. **A child is built once per request.** A child the component reads with no
   submission is built by its initializer once, on its first read in the
   request, and every later read in that request returns the same object.
   Binding a slot still runs the initializer for the child it introduces: the
   object the component's reads built is never introduced or signed, so the
   binder's refusal of an already-bound child stays as it is.

A form that needs the request's context is a child. ADR 042's form held as
state stays for a form built from its values alone; its rule for choosing
becomes: when the form's fields need the request, such as a field narrowed to
what the request may see, it is a child; otherwise, when the owner renders from
its values, it may be a form-typed attribute.

```python
class JournalEntryListComponent(QuerySetScrollComponent):
    @Glue.child
    def filters(self) -> Glue.Form:
        return Glue.form(
            target=JournalEntryFilterForm(initial={'company_id': self.request.company.pk}),
            access=Glue.Access.CHANGE,
        )

    def get_queryset(self) -> JournalEntryQuerySet:
        if not self.filters.is_valid():
            ...
        account = self.filters.cleaned_data['account']
```

```python
class JournalEntryFilterForm(forms.Form):
    account = forms.ModelChoiceField(queryset=Account.objects.none(), required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['account'].queryset = Glue.choices(
            Account.objects.active().filter(company_id=self.initial['company_id']),
            search_fields=['code', 'name'],
        )
```

## Security

Nothing a child may do changes, and nothing it carries is trusted.

- **A child's authority is still its own token.** A submission on a refresh or
  a re-render is checked exactly as one on a call is (ADR 034): its token must
  be valid for the request and match the slot's address in the owner's signed
  `children` map, its access must be above `VIEW`, and its own admission
  refuses any field it does not sign as editable. It grants the owner nothing.
- **A re-render reads only what the call produced.** The successor tokens it
  is given were issued by the server in the same request, and are checked as
  any submitted token is.
- **Choices stay narrowed by the child.** A filter's queryset comes from the
  child's `initial`, which its token signs and Glue builds and validates the
  form with on every path, never from the browser; Django validates a
  submitted id against it, and `foreign_key_choices` searches only it.
- **Children are not folded into their owner.** The owner's token still holds
  only their addresses, so token size does not grow with children.

## Consequences

- A filter can be a child form with fields narrowed to the request, searched
  on the server by `foreign_key_choices`, and bound with Spire's choice fields
  as any child form's are. A scroll list that re-renders after a row action
  keeps its filters.
- **A re-render after a call no longer resets a child to its initializer.** A
  call that wants a child cleared afterwards clears it. No known project
  relies on the reset.
- **A refresh sends each changed child.** It costs a refresh the size of those
  submissions, as a call already pays.
- **A refresh can be refused for a child.** A refresh that reads a child whose
  submitted token is malformed, from another slot, `VIEW`-only or expired is
  refused with `INVALID_CHILD_SUBMISSION`, where it used the initializer's
  child. A call is already refused the same way.
- The component's reads build a child once per request, so an initializer with
  side effects runs once for them where it ran on every read. The binder runs
  it again for a child it introduces: on the first render, and on a render
  call for a nullable, new or reintroduced child.
- The client test "a refresh carries no children, because no call reads them"
  is reversed: a refresh re-derives the owner's values, which may read a
  child.
- ADR 042's rejected alternative "a child form read outside calls" is
  superseded by this record, and its rule for choosing a form-typed attribute
  or a child is amended as above.
- Component-system §7 gains a paragraph: an island persists, so its owner reads
  it on every path and never recreates one that exists; Livewire's islands are
  its nested components, and its form objects, properties in their component's
  state, correspond to ADR 042's form held as state.
- The tests: on each path of the spike's table, an owner reads a submitted
  child's values; the re-render after a call reads a child as the call left
  it, including a change the call made to it; a child the call didn't read is
  re-rendered as submitted; a refresh carries and reads children, and refuses
  a token from another slot, a malformed token and a `VIEW` child as a call
  does; a child read twice with no submission is built once; a child at
  `CHANGE` under a `VIEW` owner is submitted on a refresh; on the client a
  refresh carries each declared child with its changes, and not a property
  child or a `VIEW` child.

## Rejected Alternatives

- **Owner-aware construction for a form held as state.** A `default_factory`
  that receives its owner, with the form built by it on every path, would let a
  form held as state narrow its own fields. It needs construction and binding
  rules for state forms, a presentation from the built form, and a second
  search call for its choices: a second way to offer model choices in a form,
  beside the child form's that already exists.
- **Folding a child's state into its owner's token.** It would end each
  child's own authority, including a child's access above its owner's
  (ADR 028), and grow the owner's token with its children, which
  component-system §7 and ADRs 004 and 025 reject.
- **Choices supplied by the component beside a form held as state.** Spire's
  `choices` option on its search field does this for an id held in an
  `IntegerField`. The choices are not searched on the server, and Django does
  not validate the id against them.
- **Leaving the three paths and asking filters not to re-render.** It keeps a
  trap: a list that re-renders after any call, or a refresh, silently loses
  its filters.
