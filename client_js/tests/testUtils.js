import "../../client_js/tests/setup"
import GluePolicy from "../src/policy"

function policyData(overrides = {}) {
    const attributes = (overrides.attributes || ['id', 'name', 'birthday', 'save']).map(attribute => {
        if (!(attribute instanceof GluePolicy)) return attribute
        const {token, ...nestedPolicy} = attribute
        return nestedPolicy
    })

    return {
        session_id: 'session-1',
        name: overrides.name || 'gorilla',
        namespace: overrides.namespace || 'model',
        access: 'change',
        identity: {
            target_pk: 1,
            pk_field_name: 'id',
            ...overrides.identity,
        },
        attributes,
        created_at: 1,
        ...overrides,
        attributes,
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

function createManifest({policy = {}, ...overrides} = {}) {
    return {
        is_glue_manifest: true,
        policy_token: createPolicyToken(policy),
        state: createState(),
        metadata: createMetadata(),
        loading_strategy: 'lazy',
        ...overrides,
    }
}

function createMetadata(overrides = {}) {
    const fields = {
        id: {namespace: 'field', type: 'AutoField', label: 'ID'},
        name: {namespace: 'field', type: 'CharField', label: 'Name'},
        birthday: {namespace: 'field', type: 'DateField', label: 'Birthday'},
        ...(overrides.fields || {}),
    }

    Object.values(fields).forEach(field => {
        field.namespace ||= 'field'
    })

    return {
        ...overrides,
        namespace: 'model',
        attributes: {
            ...fields,
            save: {namespace: 'callable'},
            ...(overrides.attributes || {}),
        },
    }
}

function createState(overrides = {}) {
    const instanceData = overrides.instance_data || {}
    const state = {
        id: {value: 1},
        name: {value: 'Koko'},
        birthday: {value: '1971-07-04'},
        ...Object.fromEntries(Object.entries(instanceData).map(([key, value]) => [key, {value}])),
        ...overrides,
    }
    delete state.instance_data

    return state
}

function mockOperationFetch(payload = {}) {
    const calls = []
    global.fetch = async (url, options) => {
        calls.push({url, options})
        return new Response(JSON.stringify({
            result: {},
            state: createState({instance_data: {id: 1, name: 'Michael', birthday: '1973-03-01'}}),
            policy_token: createPolicyToken(),
            metadata: createMetadata(),
            messages: [],
            ...payload,
        }), {
            status: payload.status || 200,
            headers: {'Content-Type': 'application/json'},
        })
    }
    return calls
}

export {createManifest, createPolicy, createPolicyToken, createMetadata, createState, mockOperationFetch}
