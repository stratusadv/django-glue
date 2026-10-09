// The wire format shared with the Django server (design/specs/core/state-model.md
// §10). Each type names the Python that produces or parses it; that Python is
// the authority, and a change there is a change here.
//
// Only what every Glue object shares lives here. Shapes one namespace owns
// (a queryset's result, a component's reactions) belong beside its proxy.

// GlueAccess in django_glue/access.py.
export type GlueAccess = 'view' | 'add' | 'change' | 'delete'

// GlueCallableCapability, GlueQueryCapability and GlueCapability in
// django_glue/glue/policy.py.
export interface GlueCallableCapability {
    allowed_arguments: string[]
}

export interface GlueQueryCapability {
    filters: Record<string, string[]>
    ordering: string[]
}

export interface GlueCapability {
    callables: Record<string, GlueCallableCapability>
    query: GlueQueryCapability | null
}

// Each Glue class builds its own identity in get_identity(). These are the
// keys the client reads; the rest pass through unread.
export interface GlueIdentity {
    pk_field_name?: string
    target_pk?: unknown
    model_class_path?: string
    form_class_path?: string
    relation?: unknown
    item_keys?: string[]
    ancestors?: string[]
    [key: string]: unknown
}

// The payload a policy token decodes to: GluePolicy.model_dump(exclude={'token'})
// in django_glue/glue/policy.py. The client reads it and never verifies it.
export interface GluePolicyPayload {
    session_id: string
    request_user_id: unknown
    name: string
    namespace: string
    identity: GlueIdentity
    access: GlueAccess
    attributes: (string | GluePolicyPayload)[]
    address: string
    children: Record<string, string>
    state_snapshot: Record<string, unknown>
    capability: GlueCapability
    created_at: number
}

// A field's choice. _field_schema() in glue/objects/django/field_adapter.py
// sends value and label; GlueRelatedModelChoices.serialize_item() in
// glue/options/django/choices.py adds obj and has_html_label.
export interface GlueChoice {
    value: unknown
    label: string
    obj?: Record<string, unknown>
    has_html_label?: boolean
}

// One entry of static_data.fields. A value attribute without an adapter sends
// only value_path and editable (BaseGlue.get_static_data() in glue/base.py);
// the field adapters' schema() in glue/objects/django/field_adapter.py sends
// the rest.
export interface GlueFieldDescriptor {
    value_path: string
    editable: boolean
    namespace?: 'field'
    type?: string
    label?: string
    required?: boolean
    help_text?: string
    disabled?: boolean
    max_length?: number
    min_length?: number
    widget?: string
    choices?: GlueChoice[]
    choice_field?: string
    pk_field?: string
    choice_model_path?: string
    related_model?: string
    choices_searchable?: boolean
}

export interface GlueChildSlot {
    kind: string
    nullable: boolean
}

export interface GlueCallableSchema {
    allowed_arguments: string[]
    returns_glue: boolean
}

// BaseGlue.get_static_data() in glue/base.py. Each key is omitted when empty.
export interface GlueStaticData {
    fields?: Record<string, GlueFieldDescriptor>
    children?: Record<string, GlueChildSlot>
    callables?: Record<string, GlueCallableSchema>
    events?: string[]
}

// One entry of computed_data.fields: the field adapters' computed_data() in
// glue/objects/django/field_adapter.py.
export interface GlueFieldComputed {
    errors: string[]
    selected_choice?: GlueChoice
    selected_choices?: GlueChoice[]
    choices_cache_key?: string
}

// BaseGlue.get_computed_data() in glue/base.py: derived values by path, and
// adapter output under `fields`. An omitted key means the previous value stands.
export interface GlueComputedData {
    fields?: Record<string, GlueFieldComputed>
    [path: string]: unknown
}

// GlueMessage.to_dict() in django_glue/message.py.
export interface GlueMessage {
    level: number
    level_tag: string
    message: string
    tags: string
}

// emit_event() in django_glue/glue/event.py.
export interface GlueEmittedEvent {
    name: string
    detail: Record<string, unknown>
}

// BaseGlue._effects_payload() in glue/base.py.
export interface GlueEffects {
    messages: GlueMessage[]
    redirect?: {url: string}
    dispose?: string[]
    events?: GlueEmittedEvent[]
}

// An entry that introduces an object, on page load or beside the call that
// produced it: GlueObjectEntry in django_glue/glue/context.py.
export interface GlueObjectEntry {
    address: string
    policy_token: string
    static_data: GlueStaticData
    computed_data: GlueComputedData
}

// The entry answering a requested address: BaseGlue._refresh_entry() and the
// call path beside it in glue/base.py. The token, static data and computed
// data are each omitted when unchanged.
export interface GlueAddressedEntry {
    address: string
    policy_token?: string
    static_data?: GlueStaticData
    computed_data?: GlueComputedData
    result: unknown
    html?: string
    effects: GlueEffects
}

// An error as the browser receives it, whether one object's call failed or
// the whole request did: GlueResponse.error_data() in django_glue/response.py.
export interface GlueErrorData {
    code: string
    message: string
    status: number
    details: Record<string, unknown>
}

// A requested address that failed: GlueAttributeCallResolver._error_entry() in
// django_glue/resolver/attribute_call/resolver.py.
export interface GlueErrorEntry {
    address: string
    error: GlueErrorData
}

export type GlueResponseEntry = GlueAddressedEntry | GlueObjectEntry | GlueErrorEntry

export interface GlueAttributeCallResponse {
    objects: GlueResponseEntry[]
}

// A fault in the request as a whole, sent with an error status and no objects:
// GlueResponse.from_error() in django_glue/response.py.
export interface GlueEnvelopeFault {
    result: {
        error: GlueErrorData
    }
    messages: GlueMessage[]
}

// AttributeCall and AddressedObjectEntry in
// django_glue/resolver/attribute_call/context.py.
export interface GlueAttributeCall {
    attribute: string
    kwargs: Record<string, unknown>
}

export interface GlueRequestEntry {
    address: string
    policy_token: string
    updates: Record<string, unknown>
    call?: GlueAttributeCall
    reintroduce?: string[]
    mounted?: string[]
}

// What Glue.view() receives: GlueViewResponseMiddleware in
// django_glue/middleware.py.
export interface GlueViewResponse {
    is_glue_template_response: true
    html: string
    objects: GlueObjectEntry[]
}

// The page context `new GlueClient(context)` receives:
// GlueContextManager._glue_client_context in django_glue/glue/context.py.
export interface GlueClientContext {
    objects: GlueObjectEntry[]
    urls: {
        callable_attribute: string
    }
    config: {
        requestTimeoutSeconds: number
        csrfCookieName: string
        glueViewMediaType: string
    }
}
