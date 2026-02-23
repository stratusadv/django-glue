import { BaseGlueProxy } from '../../src/proxies/base';
import { createMockFetch, createMockContextData, setupCookieMock } from '../testUtils';

jest.mock('../../src/constants', () => ({
    actionUrl: '/django_glue/',
    keepLiveUrl: '/django_glue/keep_live/'
}));

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
        it('sets uniqueName from constructor params', () => {
            const contextData = createMockContextData({}, { get: {} });
            const proxy = new BaseGlueProxy({
                proxyUniqueName: 'test_proxy',
                contextData,
                actions: { get: {} }
            });

            expect(proxy.uniqueName).toBe('test_proxy');
        });

        it('uses actions from contextData if not provided', () => {
            const contextData = createMockContextData({}, { save: {}, delete: {} });
            const proxy = new BaseGlueProxy({
                proxyUniqueName: 'test_proxy',
                contextData
            });

            expect(proxy.actions).toEqual({ save: {}, delete: {} });
        });

        it('prefers actions parameter over contextData.actions', () => {
            const contextData = createMockContextData({}, { save: {} });
            const proxy = new BaseGlueProxy({
                proxyUniqueName: 'test_proxy',
                contextData,
                actions: { custom: {} }
            });

            expect(proxy.actions).toEqual({ custom: {} });
        });

        it('stores contextData for subclass access', () => {
            const contextData = createMockContextData({ id: {} }, { get: {} });
            const proxy = new BaseGlueProxy({
                proxyUniqueName: 'test_proxy',
                contextData
            });

            expect(proxy.contextData).toBe(contextData);
        });

        it('sets autoFetch from constructor params', () => {
            const contextData = createMockContextData({}, { get: {} });
            const proxy = new BaseGlueProxy({
                proxyUniqueName: 'test_proxy',
                contextData,
                autoFetch: true
            });

            expect(proxy.autoFetch).toBe(true);
        });
    });

    describe('defineActionsAsProperties', () => {
        it('creates callable methods for each action', () => {
            global.fetch = createMockFetch({
                '/django_glue/': { ok: true, data: { result: 'ok' } }
            });

            const contextData = createMockContextData({}, { customAction: {} });
            const proxy = new BaseGlueProxy({
                proxyUniqueName: 'test_proxy',
                contextData
            });

            expect(typeof proxy.customAction).toBe('function');
        });

        it('does not override existing methods', () => {
            class TestProxy extends BaseGlueProxy {
                get() { return 'overridden'; }
            }

            const contextData = createMockContextData({}, { get: {} });
            const proxy = new TestProxy({
                proxyUniqueName: 'test_proxy',
                contextData
            });

            expect(proxy.get()).toBe('overridden');
        });

        it('action methods call processAction', async () => {
            global.fetch = jest.fn().mockResolvedValue({
                ok: true,
                text: () => Promise.resolve('{"result": "success"}'),
                json: () => Promise.resolve({ result: 'success' }),
                clone: function() { return this; }
            });

            const contextData = createMockContextData({}, { myAction: {} });
            const proxy = new BaseGlueProxy({
                proxyUniqueName: 'test_proxy',
                contextData
            });

            const result = await proxy.myAction({ some: 'data' });

            expect(result).toEqual({ result: 'success' });
            expect(global.fetch).toHaveBeenCalled();
        });
    });

    describe('processAction', () => {
        it('sends action request with correct payload', async () => {
            global.fetch = jest.fn().mockResolvedValue({
                ok: true,
                text: () => Promise.resolve('{"result": "success"}'),
                json: () => Promise.resolve({ result: 'success' }),
                clone: function() { return this; }
            });

            const contextData = createMockContextData({}, { save: { payload: {} } });
            const proxy = new BaseGlueProxy({
                proxyUniqueName: 'my_proxy',
                contextData
            });

            await proxy.processAction('save', { field: 'value' });

            expect(global.fetch).toHaveBeenCalledWith(
                '/django_glue/',
                expect.objectContaining({
                    body: JSON.stringify({
                        unique_name: 'my_proxy',
                        action: 'save',
                        payload: { field: 'value' }
                    })
                })
            );
        });

        it('uses stored payload when none provided', async () => {
            global.fetch = jest.fn().mockResolvedValue({
                ok: true,
                text: () => Promise.resolve('{}'),
                json: () => Promise.resolve({}),
                clone: function() { return this; }
            });

            const contextData = createMockContextData({}, { save: { payload: { stored: 'data' } } });
            const proxy = new BaseGlueProxy({
                proxyUniqueName: 'my_proxy',
                contextData
            });

            await proxy.processAction('save');

            expect(global.fetch).toHaveBeenCalledWith(
                '/django_glue/',
                expect.objectContaining({
                    body: JSON.stringify({
                        unique_name: 'my_proxy',
                        action: 'save',
                        payload: { stored: 'data' }
                    })
                })
            );
        });

        it('returns response data', async () => {
            global.fetch = jest.fn().mockResolvedValue({
                ok: true,
                text: () => Promise.resolve('{"id": 1, "name": "test"}'),
                json: () => Promise.resolve({ id: 1, name: 'test' }),
                clone: function() { return this; }
            });

            const contextData = createMockContextData({}, { get: {} });
            const proxy = new BaseGlueProxy({
                proxyUniqueName: 'test',
                contextData
            });

            const result = await proxy.processAction('get');

            expect(result).toEqual({ id: 1, name: 'test' });
        });
    });

    describe('setActionPayload / getActionPayload', () => {
        it('sets and gets payload for action', () => {
            const contextData = createMockContextData({}, { save: { payload: null } });
            const proxy = new BaseGlueProxy({
                proxyUniqueName: 'test',
                contextData
            });

            proxy.setActionPayload('save', { id: 1 });

            expect(proxy.getActionPayload('save')).toEqual({ id: 1 });
        });

        it('overwrites existing payload', () => {
            const contextData = createMockContextData({}, { save: { payload: { old: 'data' } } });
            const proxy = new BaseGlueProxy({
                proxyUniqueName: 'test',
                contextData
            });

            proxy.setActionPayload('save', { new: 'data' });

            expect(proxy.getActionPayload('save')).toEqual({ new: 'data' });
        });
    });

    describe('postInit', () => {
        it('is called during construction', () => {
            const postInitSpy = jest.fn();

            class TestProxy extends BaseGlueProxy {
                postInit() {
                    postInitSpy();
                }
            }

            const contextData = createMockContextData({}, {});
            new TestProxy({ proxyUniqueName: 'test', contextData });

            expect(postInitSpy).toHaveBeenCalled();
        });
    });
});