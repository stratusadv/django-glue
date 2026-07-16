import "../../client_js/tests/setup"

function createPolicy(overrides = {}) {
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
        attributes: overrides.attributes || ['id', 'name', 'birthday', 'save'],
        created_at: 1,
        original_signature: 'signature',
        ...overrides,
    }
}

function createMetadata(overrides = {}) {
    return {
        namespace: 'model',
        fields: {
            id: {type: 'AutoField', label: 'ID'},
            name: {type: 'CharField', label: 'Name'},
            birthday: {type: 'DateField', label: 'Birthday'},
        },
        attributes: {
            save: {namespace: 'callable'},
        },
        ...overrides,
    }
}

function createState(overrides = {}) {
    return {
        instance_data: {
            id: 1,
            name: 'Koko',
            birthday: '1971-07-04',
        },
        errors: {},
        ...overrides,
    }
}

function mockOperationFetch(payload = {}) {
    const calls = []
    global.fetch = async (url, options) => {
        calls.push({url, options})
        return new Response(JSON.stringify({
            result: {},
            state: createState({instance_data: {id: 1, name: 'Michael', birthday: '1973-03-01'}}),
            policy: createPolicy({original_signature: 'next-signature'}),
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

export {createPolicy, createMetadata, createState, mockOperationFetch}
