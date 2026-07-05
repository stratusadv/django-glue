import { describe, it, expect, beforeEach, afterEach, mock } from 'bun:test';
import GlueModelProxy from '../../src/proxies/model';
import { createMockcontract, setupCookieMock } from '../testUtils';

describe('GlueModelProxy', () => {
    let originalFetch;

    const createMockHttp = (response = { data: {} }) => ({
        sendActionRequest: mock(() => Promise.resolve(response))
    });

    beforeEach(() => {
        originalFetch = global.fetch;
        setupCookieMock({ csrftoken: 'test-token' });
    });

    afterEach(() => {
        global.fetch = originalFetch;
    });

    describe('constructor', () => {
        it('creates field accessors from contract.fields', () => {
            const http = createMockHttp();
            const contract = createMockcontract(
                { title: {}, done: {} },
                { get: {}, save: {}, delete: {} }
            );

            const proxy = new GlueModelProxy({
                http,
                proxyUniqueName: 'task',
                contract,
                values: { title: 'Test', done: false }
            });

            expect(proxy.title).toBe('Test');
            expect(proxy.done).toBe(false);
        });

        it('allows setting field values', () => {
            const http = createMockHttp();
            const contract = createMockcontract(
                { title: {} },
                { get: {}, save: {} }
            );

            const proxy = new GlueModelProxy({
                http,
                proxyUniqueName: 'task',
                contract,
                values: { title: 'Original' }
            });

            proxy.title = 'Updated';

            expect(proxy.title).toBe('Updated');
            expect(proxy._values.title).toBe('Updated');
        });

        it('initializes _values object when setting if null', () => {
            const http = createMockHttp();
            const contract = createMockcontract(
                { title: {} },
                { get: {}, save: {} }
            );

            const proxy = new GlueModelProxy({
                http,
                proxyUniqueName: 'task',
                contract,
                values: null
            });

            proxy.title = 'New Value';

            expect(proxy._values).toEqual({ title: 'New Value' });
        });

        it('stores passed values', () => {
            const http = createMockHttp();
            const contract = createMockcontract(
                { id: {}, title: {} },
                { get: {} }
            );

            const proxy = new GlueModelProxy({
                http,
                proxyUniqueName: 'task',
                contract,
                values: { id: 1, title: 'Test' }
            });

            expect(proxy._values).toEqual({ id: 1, title: 'Test' });
        });

        it('creates $key property', () => {
            const http = createMockHttp();
            const contract = createMockcontract({}, {});

            const proxy = new GlueModelProxy({
                http,
                proxyUniqueName: 'task',
                contract,
                values: { id: 1 }
            });

            expect(proxy.$key).toMatch(/^django-glue-\d+$/);
        });

        it('creates $fields object', () => {
            const http = createMockHttp();
            const contract = createMockcontract({ name: {} }, {});

            const proxy = new GlueModelProxy({
                http,
                proxyUniqueName: 'task',
                contract,
                values: { name: 'test' }
            });

            expect(proxy.$fields).toBeDefined();
            expect(proxy.$fields.name).toBeDefined();
        });

        it('defines extra fields not in contract.fields', () => {
            const http = createMockHttp();
            const contract = createMockcontract(
                { id: {} },
                {}
            );

            const proxy = new GlueModelProxy({
                http,
                proxyUniqueName: 'task',
                contract,
                values: { id: 1, extra_field: 'extra' }
            });

            expect(proxy.extra_field).toBe('extra');
        });
    });

    describe('_isNew', () => {
        it('returns true when values.id is falsy', () => {
            const http = createMockHttp();
            const contract = createMockcontract({}, {});

            const proxy = new GlueModelProxy({
                http,
                proxyUniqueName: 'task',
                contract,
                values: { title: 'New' }
            });

            expect(proxy._isNew).toBe(true);
        });

        it('returns true when values is null', () => {
            const http = createMockHttp();
            const contract = createMockcontract({}, {});

            const proxy = new GlueModelProxy({
                http,
                proxyUniqueName: 'task',
                contract,
                values: null
            });

            expect(proxy._isNew).toBe(true);
        });

        it('returns false when values.id is set', () => {
            const http = createMockHttp();
            const contract = createMockcontract({}, {});

            const proxy = new GlueModelProxy({
                http,
                proxyUniqueName: 'task',
                contract,
                values: { id: 1, title: 'Existing' }
            });

            expect(proxy._isNew).toBe(false);
        });
    });

    describe('get', () => {
        it('calls _processAction with get action', async () => {
            let capturedAction = null;
            const mockHttp = {
                sendActionRequest: mock((req) => {
                    capturedAction = req.action;
                    return Promise.resolve({ data: { id: 1, title: 'Fetched' } });
                })
            };

            const contract = createMockcontract({ title: {} }, {});
            const proxy = new GlueModelProxy({
                http: mockHttp,
                proxyUniqueName: 'task',
                contract,
                values: { id: 0 }
            });

            await proxy.get();

            expect(capturedAction).toBe('get');
            expect(proxy._values).toEqual({ id: 1, title: 'Fetched' });
            expect(proxy._loaded).toBe(true);
        });

        it('delegates to parent queryset when _parent exists', async () => {
            let capturedAction = null;
            let capturedPayload = null;
            const parentMockHttp = {
                sendActionRequest: mock((req) => {
                    capturedAction = req.action;
                    capturedPayload = req.payload;
                    return Promise.resolve({ data: { id: 5, title: 'From Parent' } });
                })
            };

            const parentcontract = createMockcontract({}, { get: {} });
            const parent = {
                http: parentMockHttp,
                _uniqueName: 'tasks',
                _contract: parentcontract,
                _actions: { get: {} },
                _listeners: { before: {}, after: {}, error: {} },
                _processAction: async function(actionName, data) {
                    const response = await this.http.sendActionRequest({
                        uniqueName: this._uniqueName,
                        action: actionName,
                        payload: data,
                        contract: this._contract
                    });
                    return response.data;
                }
            };

            const contract = createMockcontract({ title: {} }, {});
            const proxy = new GlueModelProxy({
                http: parentMockHttp,
                proxyUniqueName: 'tasks',
                contract,
                values: { id: 0 },
                parentQuerySet: parent
            });

            await proxy.get(5);

            expect(capturedAction).toBe('get');
            expect(capturedPayload).toEqual({ id: 5 });
            expect(proxy._values).toEqual({ id: 5, title: 'From Parent' });
        });
    });

    describe('delete', () => {
        it('sends delete action for existing instance', async () => {
            let capturedPayload = null;
            const mockHttp = {
                sendActionRequest: mock((req) => {
                    capturedPayload = req.payload;
                    return Promise.resolve({ data: { deleted: true } });
                })
            };

            const contract = createMockcontract({ title: {} }, {});
            const proxy = new GlueModelProxy({
                http: mockHttp,
                proxyUniqueName: 'task',
                contract,
                values: { id: 1 }
            });

            const result = await proxy.delete();

            expect(capturedPayload).toEqual({ id: 1 });
            expect(result).toEqual({ deleted: true });
        });

        it('calls parent refresh for new instance with parent', async () => {
            const refreshSpy = mock(() => Promise.resolve());
            const parent = {
                refresh: refreshSpy
            };

            const contract = createMockcontract({}, {});
            const proxy = new GlueModelProxy({
                http: createMockHttp(),
                proxyUniqueName: 'tasks',
                contract,
                values: { title: 'New' },
                parentQuerySet: parent
            });

            const result = await proxy.delete();

            expect(refreshSpy).toHaveBeenCalled();
            expect(result).toEqual({ success: true });
        });

        it('calls parent refresh after deleting existing instance', async () => {
            const refreshSpy = mock(() => Promise.resolve());
            const mockHttp = {
                sendActionRequest: mock(() => Promise.resolve({ data: { deleted: true } })),
            };
            const parent = {
                refresh: refreshSpy
            };

            const contract = createMockcontract({}, {});
            const proxy = new GlueModelProxy({
                http: mockHttp,
                proxyUniqueName: 'tasks',
                contract,
                values: { id: 1 },
                parentQuerySet: parent
            });

            await proxy.delete();

            expect(refreshSpy).toHaveBeenCalled();
        });
    });

    describe('inherits from GlueFormProxy', () => {
        it('can call validate', async () => {
            const mockHttp = {
                sendActionRequest: mock(() => Promise.resolve({
                    data: { success: true, errors: {} }
                }))
            };

            const contract = createMockcontract({ name: {} }, {});
            const proxy = new GlueModelProxy({
                http: mockHttp,
                proxyUniqueName: 'task',
                contract,
                values: { name: 'test' }
            });

            const result = await proxy.validate();
            expect(result).toEqual({ success: true, errors: {} });
        });

        it('can call save', async () => {
            const mockHttp = {
                sendActionRequest: mock(() => Promise.resolve({
                    data: { success: true, errors: {} }
                }))
            };

            const contract = createMockcontract({ name: {} }, {});
            const proxy = new GlueModelProxy({
                http: mockHttp,
                proxyUniqueName: 'task',
                contract,
                values: { name: 'test' }
            });

            const result = await proxy.save();
            expect(result.success).toBe(true);
        });

        it('has hasErrors method', () => {
            const http = createMockHttp();
            const contract = createMockcontract({ name: {} }, {});
            const proxy = new GlueModelProxy({
                http,
                proxyUniqueName: 'task',
                contract,
                values: { name: 'test' }
            });

            expect(proxy.hasErrors()).toBe(false);
            proxy._errors = { name: ['Error'] };
            expect(proxy.hasErrors()).toBe(true);
        });
    });
});
