import "../../client_js/tests/setup"
import GluePolicy from "../src/policy"

function policyData(overrides = {}) {
    const name = overrides.name || 'gorilla'
    const namespace = overrides.namespace || 'model'
    return {
        session_id: 'session-1',
        request_user_id: 1,
        name,
        namespace,
        access: 'change',
        identity: {
            target_pk: 1,
            pk_field_name: 'id',
            ...overrides.identity,
        },
        attributes: overrides.attributes || ['id', 'name', 'birthday', 'save'],
        address: overrides.address || `${name}#test`,
        children: overrides.children || {},
        state_snapshot: overrides.state_snapshot || {
            id: 1,
            name: 'Koko',
            birthday: '1971-07-04',
        },
        capability: overrides.capability || {callables: {}},
        created_at: 1,
        ...overrides,
    }
}

function createPolicyToken(overrides = {}) {
    const bytes = new TextEncoder().encode(JSON.stringify(policyData(overrides)))
    const binary = Array.from(bytes, byte => String.fromCharCode(byte)).join('')
    const payload = btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
    return `${payload}:test-timestamp:test-signature`
}

function createPolicy(overrides = {}) {
    return GluePolicy.fromSignedPolicyToken(createPolicyToken(overrides))
}

function createStaticData(overrides = {}) {
    return {
        fields: {
            id: {value_path: 'id', type: 'AutoField', label: 'ID', editable: false},
            name: {value_path: 'name', type: 'CharField', label: 'Name', editable: true},
            birthday: {value_path: 'birthday', type: 'DateField', label: 'Birthday', editable: true},
            ...(overrides.fields || {}),
        },
        callables: {
            save: {allowed_arguments: []},
            ...(overrides.callables || {}),
        },
        ...(overrides.params ? {params: overrides.params} : {}),
        ...(overrides.children ? {children: overrides.children} : {}),
    }
}

function createManifest({policy = {}, staticData = {}, computedData = {}, ...overrides} = {}) {
    const normalizedPolicy = policyData(policy)
    return {
        is_glue_manifest: true,
        address: normalizedPolicy.address,
        policy_token: createPolicyToken(normalizedPolicy),
        static_data: createStaticData(staticData),
        computed_data: computedData,
        loading_strategy: 'eager',
        ...overrides,
    }
}

// Page-load wire entry (state-model.md §10): the manifest shape without the
// phase-5 result tag.
function createEntry(overrides = {}) {
    const manifest = createManifest(overrides)
    const {is_glue_manifest, ...entry} = manifest
    return entry
}

function createState(overrides = {}) {
    return {
        id: 1,
        name: 'Koko',
        birthday: '1971-07-04',
        ...(overrides.instance_data || {}),
        ...Object.fromEntries(
            Object.entries(overrides).filter(([key]) => key !== 'instance_data')
        ),
    }
}

function mockOperationFetch(payload = {}) {
    const calls = []
    global.fetch = async (url, options) => {
        calls.push({url, options})
        return new Response(JSON.stringify({objects: [], ...payload}), {
            status: payload.status || 200,
            headers: {'Content-Type': 'application/json'},
        })
    }
    return calls
}

// Wire shapes for attribute-call responses (state-model.md §10):
// {objects: [entry, ...]} where each entry is addressed and carries
// policy_token / static_data / computed_data (omitted when unchanged),
// result, and effects.

function objectsEnvelope(entries) {
    return {data: {objects: entries}}
}

function attributeResponse(address, fields = {}) {
    return objectsEnvelope([{address, ...fields}])
}

export {
    attributeResponse,
    createEntry,
    createManifest,
    createPolicy,
    createPolicyToken,
    createState,
    createStaticData,
    mockOperationFetch,
    objectsEnvelope,
    policyData,
}
