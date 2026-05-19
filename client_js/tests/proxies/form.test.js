import { describe, it, expect, beforeEach, afterEach, mock } from 'bun:test';
import { GlueFormProxy } from '../../src/proxies/form';
import { setupCookieMock } from '../testUtils';

describe('GlueFormProxy', () => {
    let originalFetch;

    const createMockHttp = (response = { data: { success: true, errors: {} } }) => ({
        sendActionRequest: mock(() => Promise.resolve(response))
    });

    function createFormContextData(fields = {}, initial = {}, actions = {}) {
        return {
            fields: fields,
            initial: initial,
            actions: Object.keys(actions).length ? actions : { get: {}, validate: {}, save: {} }
        };
    }

    beforeEach(() => {
        originalFetch = global.fetch;
        setupCookieMock({ csrftoken: 'test-token' });
    });

    afterEach(() => {
        global.fetch = originalFetch;
    });

    describe('constructor', () => {
        it('creates field accessors from contextData.fields', () => {
            const http = createMockHttp();
            const contextData = createFormContextData(
                { name: { type: 'text' }, email: { type: 'email' } },
                { name: 'John', email: 'john@example.com' }
            );

            const proxy = new GlueFormProxy({
                http,
                proxyUniqueName: 'contact_form',
                contextData
            });

            expect(proxy.name).toBe('John');
            expect(proxy.email).toBe('john@example.com');
        });

        it('initializes _values from contextData.initial', () => {
            const http = createMockHttp();
            const contextData = createFormContextData(
                { title: {} },
                { title: 'Initial Value' }
            );

            const proxy = new GlueFormProxy({
                http,
                proxyUniqueName: 'form',
                contextData
            });

            expect(proxy._values).toEqual({ title: 'Initial Value' });
        });

        it('starts with empty _errors', () => {
            const http = createMockHttp();
            const contextData = createFormContextData({ name: {} }, {});

            const proxy = new GlueFormProxy({
                http,
                proxyUniqueName: 'form',
                contextData
            });

            expect(proxy._errors).toEqual({});
        });

        it('stores field definitions in $fields', () => {
            const http = createMockHttp();
            const contextData = createFormContextData(
                { name: { type: 'text', required: true } },
                {}
            );

            const proxy = new GlueFormProxy({
                http,
                proxyUniqueName: 'form',
                contextData
            });

            expect(proxy.$fields).toEqual({ name: { type: 'text', required: true } });
        });

        it('allows setting field values via property', () => {
            const http = createMockHttp();
            const contextData = createFormContextData({ name: {} }, { name: 'Original' });

            const proxy = new GlueFormProxy({
                http,
                proxyUniqueName: 'form',
                contextData
            });

            proxy.name = 'Updated';

            expect(proxy.name).toBe('Updated');
            expect(proxy._values.name).toBe('Updated');
        });

        it('creates PascalCase attributes for field properties', () => {
            const http = createMockHttp();
            const contextData = createFormContextData(
                { name: { type: 'text', required: true } },
                {}
            );

            const proxy = new GlueFormProxy({
                http,
                proxyUniqueName: 'form',
                contextData
            });

            expect(proxy.nameType).toBe('text');
            expect(proxy.nameRequired).toBe(true);
        });

        it('creates error attributes for fields', () => {
            const http = createMockHttp();
            const contextData = createFormContextData({ name: { type: 'text' } }, {});

            const proxy = new GlueFormProxy({
                http,
                proxyUniqueName: 'form',
                contextData
            });

            expect(proxy.nameHasErrors).toBe(false);
            // _updateErrorAttributesForField uses ?.join() which returns undefined for missing errors
            expect(proxy.nameErrorText).toBeUndefined();
        });
    });

    describe('validate', () => {
        it('sends validate action with current values', async () => {
            let capturedPayload = null;
            const mockHttp = {
                sendActionRequest: mock((req) => {
                    capturedPayload = req.payload;
                    return Promise.resolve({ data: { success: true, errors: {} } });
                })
            };

            const contextData = createFormContextData(
                { name: {} },
                { name: 'Test' }
            );

            const proxy = new GlueFormProxy({
                http: mockHttp,
                proxyUniqueName: 'form',
                contextData
            });

            const result = await proxy.validate();

            expect(capturedPayload).toEqual({ name: 'Test' });
            expect(result).toEqual({ success: true, errors: {} });
        });

        it('updates _errors from validation response', async () => {
            const mockHttp = {
                sendActionRequest: mock(() => Promise.resolve({
                    data: { success: false, errors: { name: ['Required'] } }
                }))
            };

            const contextData = createFormContextData({ name: {} }, {});

            const proxy = new GlueFormProxy({
                http: mockHttp,
                proxyUniqueName: 'form',
                contextData
            });

            await proxy.validate();

            expect(proxy._errors).toEqual({ name: ['Required'] });
        });

        it('updates _errors after validation', async () => {
            const mockHttp = {
                sendActionRequest: mock(() => Promise.resolve({
                    data: { success: false, errors: { name: ['Required', 'Too short'] } }
                }))
            };

            const contextData = createFormContextData({ name: { type: 'text' } }, {});

            const proxy = new GlueFormProxy({
                http: mockHttp,
                proxyUniqueName: 'form',
                contextData
            });

            await proxy.validate();

            // validate() sets _errors directly but does NOT call _updateErrors()
            expect(proxy._errors).toEqual({ name: ['Required', 'Too short'] });
        });
    });

    describe('save', () => {
        it('sends save action with FormData', async () => {
            const capturedReqs = [];
            const mockHttp = {
                sendActionRequest: function(req) {
                    capturedReqs.push(req);
                    return Promise.resolve({ data: { success: true, errors: {} } });
                }
            };

            const contextData = createFormContextData(
                { name: { type: 'text' } },
                { name: 'Submit Me' }
            );

            const proxy = new GlueFormProxy({
                http: mockHttp,
                proxyUniqueName: 'form',
                contextData
            });

            const result = await proxy.save();

            // save() triggers 'save' action, then on success calls get()
            expect(capturedReqs.length).toBeGreaterThanOrEqual(1);
            const saveReq = capturedReqs.find(r => r.action === 'save');
            expect(saveReq).not.toBeNull();
            expect(saveReq.payload).toBeInstanceOf(FormData);
            expect(result.success).toBe(true);
        });

        it('updates _errors from save response', async () => {
            const mockHttp = {
                sendActionRequest: mock(() => Promise.resolve({
                    data: { success: false, errors: { email: ['Invalid email'] } }
                }))
            };

            const contextData = createFormContextData({ email: {} }, { email: 'bad' });

            const proxy = new GlueFormProxy({
                http: mockHttp,
                proxyUniqueName: 'form',
                contextData
            });

            await proxy.save();

            expect(proxy._errors).toEqual({ email: ['Invalid email'] });
        });

        it('clears errors on successful save', async () => {
            const mockHttp = {
                sendActionRequest: mock(() => Promise.resolve({
                    data: { success: true, errors: {} }
                }))
            };

            const contextData = createFormContextData({ name: {} }, { name: 'Valid' });

            const proxy = new GlueFormProxy({
                http: mockHttp,
                proxyUniqueName: 'form',
                contextData
            });

            proxy._errors = { name: ['Old error'] };
            await proxy.save();

            expect(proxy._errors).toEqual({});
        });
    });

    describe('hasErrors', () => {
        it('returns false when no errors', () => {
            const http = createMockHttp();
            const contextData = createFormContextData({ name: {} }, {});
            const proxy = new GlueFormProxy({ http, proxyUniqueName: 'form', contextData });

            expect(proxy.hasErrors()).toBe(false);
        });

        it('returns true when errors exist', () => {
            const http = createMockHttp();
            const contextData = createFormContextData({ name: {} }, {});
            const proxy = new GlueFormProxy({ http, proxyUniqueName: 'form', contextData });

            proxy._errors = { name: ['Error'] };
            expect(proxy.hasErrors()).toBe(true);
        });

        it('returns true for specific field with errors', () => {
            const http = createMockHttp();
            const contextData = createFormContextData({ name: { type: 'text' }, email: { type: 'email' } }, {});
            const proxy = new GlueFormProxy({ http, proxyUniqueName: 'form', contextData });

            proxy._errors = { name: ['Error'] };
            expect(proxy.hasErrors('name')).toBe(true);
            // hasErrors returns undefined for field without errors (truthy check needed)
            expect(proxy.hasErrors('email')).toBeFalsy();
        });
    });

    describe('_clearErrors', () => {
        it('removes all errors', () => {
            const http = createMockHttp();
            const contextData = createFormContextData({ name: {}, email: {} }, {});
            const proxy = new GlueFormProxy({ http, proxyUniqueName: 'form', contextData });

            proxy._errors = { name: ['Error'], email: ['Another error'] };
            proxy._clearErrors();

            expect(proxy._errors).toEqual({});
        });
    });

    describe('_getFormData', () => {
        it('converts values to FormData', () => {
            const http = createMockHttp();
            const contextData = createFormContextData({ name: {}, count: {} }, {});
            const proxy = new GlueFormProxy({ http, proxyUniqueName: 'form', contextData });

            proxy._values = { name: 'test', count: 42 };
            const formData = proxy._getFormData();

            expect(formData.get('name')).toBe('test');
            expect(formData.get('count')).toBe('42');
        });

        it('handles array values', () => {
            const http = createMockHttp();
            const contextData = createFormContextData({ tags: {} }, {});
            const proxy = new GlueFormProxy({ http, proxyUniqueName: 'form', contextData });

            proxy._values = { tags: ['a', 'b'] };
            const formData = proxy._getFormData();

            expect(formData.getAll('tags')).toEqual(['a', 'b']);
        });

        it('converts null and undefined to empty string', () => {
            const http = createMockHttp();
            const contextData = createFormContextData({ a: {}, b: {} }, {});
            const proxy = new GlueFormProxy({ http, proxyUniqueName: 'form', contextData });

            proxy._values = { a: null, b: undefined };
            const formData = proxy._getFormData();

            expect(formData.get('a')).toBe('');
            expect(formData.get('b')).toBe('');
        });
    });

    describe('get', () => {
        it('calls _processAction with get action', async () => {
            let capturedAction = null;
            const mockHttp = {
                sendActionRequest: mock((req) => {
                    capturedAction = req.action;
                    return Promise.resolve({ data: { name: 'Fetched' } });
                })
            };

            const contextData = createFormContextData({ name: {} }, {});
            const proxy = new GlueFormProxy({
                http: mockHttp,
                proxyUniqueName: 'form',
                contextData
            });

            proxy.get();
            await new Promise(resolve => setTimeout(resolve, 10));

            expect(capturedAction).toBe('get');
            expect(proxy._values).toEqual({ name: 'Fetched' });
            expect(proxy._loaded).toBe(true);
        });
    });
});
