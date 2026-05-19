import { describe, it, expect, beforeEach, afterEach, mock } from 'bun:test';
import { BaseGlueProxy } from '../../src/proxies/base';
import { createMockContextData, setupCookieMock } from '../testUtils';

describe('BaseGlueProxy', () => {
    let originalFetch;

    beforeEach(() => {
        originalFetch = global.fetch;
        setupCookieMock({ csrftoken: 'test-token' });
    });

    afterEach(() => {
        global.fetch = originalFetch;
    });

    describe('constructor', () => {
        it('stores http instance', () => {
            const http = { sendActionRequest: () => Promise.resolve({ data: {} }) };
            const contextData = createMockContextData({}, { get: {} });
            const proxy = new BaseGlueProxy({
                http,
                proxyUniqueName: 'test_proxy',
                contextData
            });

            expect(proxy.http).toBe(http);
        });

        it('stores uniqueName as private _uniqueName', () => {
            const contextData = createMockContextData({}, { get: {} });
            const proxy = new BaseGlueProxy({
                proxyUniqueName: 'test_proxy',
                contextData
            });

            expect(proxy._uniqueName).toBe('test_proxy');
        });

        it('stores contextData as private _contextData', () => {
            const contextData = createMockContextData({ id: {} }, { get: {} });
            const proxy = new BaseGlueProxy({
                proxyUniqueName: 'test_proxy',
                contextData
            });

            expect(proxy._contextData).toBe(contextData);
        });

        it('uses actions from contextData if not provided', () => {
            const contextData = createMockContextData({}, { save: {}, delete: {} });
            const proxy = new BaseGlueProxy({
                proxyUniqueName: 'test_proxy',
                contextData
            });

            expect(proxy._actions).toEqual({ save: {}, delete: {} });
        });

        it('prefers actions parameter over contextData.actions', () => {
            const contextData = createMockContextData({}, { save: {} });
            const proxy = new BaseGlueProxy({
                proxyUniqueName: 'test_proxy',
                contextData,
                actions: { custom: {} }
            });

            expect(proxy._actions).toEqual({ custom: {} });
        });

        it('initializes empty listeners', () => {
            const contextData = createMockContextData({}, {});
            const proxy = new BaseGlueProxy({
                proxyUniqueName: 'test_proxy',
                contextData
            });

            expect(proxy._listeners).toEqual({ before: {}, after: {}, error: {} });
        });
    });

    describe('addListener', () => {
        it('registers a callback for an action', () => {
            const contextData = createMockContextData({}, { save: {} });
            const proxy = new BaseGlueProxy({
                proxyUniqueName: 'test_proxy',
                contextData
            });

            const callback = () => {};
            proxy.addListener('save', callback, 'after');

            expect(proxy._listeners.after.save).toContain(callback);
        });

        it('defaults to after listener type', () => {
            const contextData = createMockContextData({}, { save: {} });
            const proxy = new BaseGlueProxy({
                proxyUniqueName: 'test_proxy',
                contextData
            });

            const callback = () => {};
            proxy.addListener('save', callback);

            expect(proxy._listeners.after.save).toContain(callback);
        });

        it('supports before, after, and error types', () => {
            const contextData = createMockContextData({}, { save: {} });
            const proxy = new BaseGlueProxy({
                proxyUniqueName: 'test_proxy',
                contextData
            });

            const cb = () => {};
            proxy.addListener('save', cb, 'before');
            proxy.addListener('save', cb, 'after');
            proxy.addListener('save', cb, 'error');

            expect(proxy._listeners.before.save).toContain(cb);
            expect(proxy._listeners.after.save).toContain(cb);
            expect(proxy._listeners.error.save).toContain(cb);
        });

        it('throws on invalid listener type', () => {
            const contextData = createMockContextData({}, { save: {} });
            const proxy = new BaseGlueProxy({
                proxyUniqueName: 'test_proxy',
                contextData
            });

            expect(() => proxy.addListener('save', () => {}, 'invalid'))
                .toThrow('Invalid listener type');
        });

        it('returns proxy for chaining', () => {
            const contextData = createMockContextData({}, { save: {} });
            const proxy = new BaseGlueProxy({
                proxyUniqueName: 'test_proxy',
                contextData
            });

            const result = proxy.addListener('save', () => {});
            expect(result).toBe(proxy);
        });
    });

    describe('removeListener', () => {
        it('removes a callback for an action', () => {
            const contextData = createMockContextData({}, { save: {} });
            const proxy = new BaseGlueProxy({
                proxyUniqueName: 'test_proxy',
                contextData
            });

            const callback = () => {};
            proxy.addListener('save', callback, 'after');
            proxy.removeListener('save', callback, 'after');

            expect(proxy._listeners.after.save).not.toContain(callback);
        });

        it('returns proxy for chaining', () => {
            const contextData = createMockContextData({}, { save: {} });
            const proxy = new BaseGlueProxy({
                proxyUniqueName: 'test_proxy',
                contextData
            });

            const result = proxy.removeListener('save', () => {});
            expect(result).toBe(proxy);
        });
    });

    describe('clearListeners', () => {
        it('removes all listeners', () => {
            const contextData = createMockContextData({}, { save: {} });
            const proxy = new BaseGlueProxy({
                proxyUniqueName: 'test_proxy',
                contextData
            });

            proxy.addListener('save', () => {}, 'before');
            proxy.addListener('save', () => {}, 'after');
            proxy.clearListeners();

            expect(proxy._listeners).toEqual({});
        });

        it('returns proxy for chaining', () => {
            const contextData = createMockContextData({}, {});
            const proxy = new BaseGlueProxy({
                proxyUniqueName: 'test_proxy',
                contextData
            });

            const result = proxy.clearListeners();
            expect(result).toBe(proxy);
        });
    });

    describe('_processAction', () => {
        it('sends action request with correct params', async () => {
            let capturedRequest = null;
            const mockHttp = {
                sendActionRequest: mock((req) => {
                    capturedRequest = req;
                    return Promise.resolve({ data: { result: 'success' } });
                })
            };

            const contextData = createMockContextData({}, { save: {} });
            const proxy = new BaseGlueProxy({
                http: mockHttp,
                proxyUniqueName: 'my_proxy',
                contextData
            });

            const result = await proxy._processAction('save', { field: 'value' });

            expect(capturedRequest).toEqual({
                uniqueName: 'my_proxy',
                action: 'save',
                payload: { field: 'value' },
                contextData
            });
            expect(result).toEqual({ result: 'success' });
        });

        it('fires before listeners before request', async () => {
            let order = [];
            const mockHttp = {
                sendActionRequest: mock(() => {
                    order.push('request');
                    return Promise.resolve({ data: { result: 'ok' } });
                })
            };

            const contextData = createMockContextData({}, { save: {} });
            const proxy = new BaseGlueProxy({
                http: mockHttp,
                proxyUniqueName: 'test',
                contextData
            });

            proxy.addListener('save', () => { order.push('before'); }, 'before');

            await proxy._processAction('save', { data: 'test' });

            expect(order).toEqual(['before', 'request']);
        });

        it('fires after listeners with result', async () => {
            let capturedEvent = null;
            const mockHttp = {
                sendActionRequest: mock(() => Promise.resolve({ data: { id: 1 } }))
            };

            const contextData = createMockContextData({}, { save: {} });
            const proxy = new BaseGlueProxy({
                http: mockHttp,
                proxyUniqueName: 'test',
                contextData
            });

            proxy.addListener('save', (event) => { capturedEvent = event; }, 'after');
            await proxy._processAction('save', { data: 'test' });

            expect(capturedEvent.result).toEqual({ id: 1 });
            expect(capturedEvent.action).toBe('save');
            expect(capturedEvent.proxy).toBe(proxy);
        });

        it('fires error listeners and re-throws on failure', async () => {
            let capturedError = null;
            const mockHttp = {
                sendActionRequest: mock(() => Promise.reject(new Error('network error')))
            };

            const contextData = createMockContextData({}, { save: {} });
            const proxy = new BaseGlueProxy({
                http: mockHttp,
                proxyUniqueName: 'test',
                contextData
            });

            proxy.addListener('save', (event) => { capturedError = event.error; }, 'error');

            await expect(proxy._processAction('save', {})).rejects.toThrow('network error');
            expect(capturedError).toBeInstanceOf(Error);
        });

        it('converts FormData payload to object for event', async () => {
            let capturedPayload = null;
            const mockHttp = {
                sendActionRequest: mock(() => Promise.resolve({ data: {} }))
            };

            const contextData = createMockContextData({}, { save: {} });
            const proxy = new BaseGlueProxy({
                http: mockHttp,
                proxyUniqueName: 'test',
                contextData
            });

            proxy.addListener('save', (event) => { capturedPayload = event.payload; }, 'before');

            const formData = new FormData();
            formData.append('name', 'value');
            formData.append('name', 'value2');

            await proxy._processAction('save', formData);

            expect(capturedPayload.name).toEqual(['value', 'value2']);
        });

        it('returns response.data', async () => {
            const mockHttp = {
                sendActionRequest: mock(() => Promise.resolve({ data: { id: 1, name: 'test' } }))
            };

            const contextData = createMockContextData({}, { get: {} });
            const proxy = new BaseGlueProxy({
                http: mockHttp,
                proxyUniqueName: 'test',
                contextData
            });

            const result = await proxy._processAction('get');
            expect(result).toEqual({ id: 1, name: 'test' });
        });
    });
});
