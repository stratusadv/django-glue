import {mock} from 'bun:test';

export function createMockFetch(responses = {}) {
    return mock((url) => {
        const response = responses[url] || {ok: true, data: {}};
        return Promise.resolve({
            ok: response.ok ?? true,
            text: () => Promise.resolve(response.text ?? JSON.stringify(response.data)),
            json: () => Promise.resolve(response.data),
            clone: function () {
                return this;
            },
        });
    });
}

export function setupCookieMock(cookies = {}) {
    const cookieString = Object.entries(cookies)
        .map(([key, value]) => `${key}=${encodeURIComponent(value)}`)
        .join('; ');

    Object.defineProperty(document, 'cookie', {
        value: cookieString,
        writable: true,
        configurable: true,
    });
}

export function createPolicy(namespace = 'form', overrides = {}) {
    return {
        subject_details: {
            namespace,
            included_fields: {},
            ...overrides.subject_details,
        },
        bound_attributes: {
            [`Glue${namespace[0].toUpperCase()}${namespace.slice(1)}Proxy.load`]: {},
            ...overrides.bound_attributes,
        },
        ...Object.fromEntries(
            Object.entries(overrides).filter(
                ([key]) => !['subject_details', 'bound_attributes'].includes(key),
            ),
        ),
    };
}

export function createFormPolicy(overrides = {}) {
    return createPolicy('form', {
        subject_details: {
            included_fields: {
                name: {type: 'CharField', label: 'Name'},
                email: {type: 'EmailField', label: 'Email'},
            },
            target_pk: null,
            pk_field_name: 'id',
            ...overrides.subject_details,
        },
        bound_attributes: {
            'GlueFormProxy.load': {},
            'GlueFormProxy.validate': {},
            'GlueFormProxy.save': {},
            'GlueFormProxy.foreign_key_choices': {},
            ...overrides.bound_attributes,
        },
    });
}

export function createModelPolicy(overrides = {}) {
    return createPolicy('model', {
        subject_details: {
            included_fields: {
                id: {type: 'IntegerField', label: 'ID'},
                name: {type: 'CharField', label: 'Name'},
            },
            target_pk: 1,
            pk_field_name: 'id',
            ...overrides.subject_details,
        },
        bound_attributes: {
            'GlueModelProxy.load': {},
            'GlueModelProxy.save': {},
            'GlueModelProxy.delete': {},
            ...overrides.bound_attributes,
        },
    });
}

export function createQuerySetPolicy(overrides = {}) {
    return createPolicy('querySet', {
        subject_details: {
            pk_field_name: 'id',
            ...overrides.subject_details,
        },
        bound_attributes: {
            'GlueQuerySetProxy.query_with_params': {},
            'GlueQuerySetProxy.new': {},
            ...overrides.bound_attributes,
        },
    });
}

export function createFunctionPolicy(overrides = {}) {
    return createPolicy('function', {
        subject_details: {
            params: [{name: 'amount'}, {name: 'tax'}],
            ...overrides.subject_details,
        },
        bound_attributes: {
            'GlueFunctionProxy.execute': {},
            ...overrides.bound_attributes,
        },
    });
}

export function createTemplatePolicy(overrides = {}) {
    return createPolicy('template', {
        subject_details: {
            template_path: 'card.html',
            initial_context_data: {},
            ...overrides.subject_details,
        },
        bound_attributes: {
            'GlueTemplateProxy.render_html': {},
            ...overrides.bound_attributes,
        },
    });
}

export function createState(instanceData = {}) {
    return {
        namespace: 'form',
        instance_data: instanceData,
        errors: {},
    };
}

export function createMockHttp(responseData = {result: {}, state: {}}) {
    return {
        sendAttributeEventRequest: mock(async () => ({data: responseData})),
    };
}
