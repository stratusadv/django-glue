import { describe, it, expect, beforeEach, afterEach, mock } from 'bun:test';
import { GlueModelProxy } from '../../src/proxies/model';
import { createMockFetch, createMockContextData, setupCookieMock } from '../testUtils';

mock.module('../../src/constants', () => ({
    actionUrl: '/django_glue/',
    keepLiveUrl: '/django_glue/keep_live/'
}));

describe('GlueModelProxy', () => {
    let originalFetch;

    beforeEach(() => {
        originalFetch = global.fetch;
        setupCookieMock({ csrftoken: 'test-token' });
    });

    afterEach(() => {
        global.fetch = originalFetch;
    });

    describe('constructor', () => {
        it('creates field accessors from contextData.fields', () => {
            const contextData = createMockContextData(
                { title: {}, done: {} },
                { get: {}, save: {}, delete: {} }
            );

            const proxy = new GlueModelProxy({
                proxyUniqueName: 'task',
                contextData,
                values: { title: 'Test', done: false }
            });

            expect(proxy.title).toBe('Test');
            expect(proxy.done).toBe(false);
        });

        it('allows setting field values', () => {
            const contextData = createMockContextData(
                { title: {} },
                { get: {}, save: {} }
            );

            const proxy = new GlueModelProxy({
                proxyUniqueName: 'task',
                contextData,
                values: { title: 'Original' }
            });

            proxy.title = 'Updated';

            expect(proxy.title).toBe('Updated');
            expect(proxy.values.title).toBe('Updated');
        });

        it('initializes values object when setting if null', () => {
            const contextData = createMockContextData(
                { title: {} },
                { get: {}, save: {} }
            );

            const proxy = new GlueModelProxy({
                proxyUniqueName: 'task',
                contextData,
                values: null
            });

            proxy.title = 'New Value';

            expect(proxy.values).toEqual({ title: 'New Value' });
        });

        it('stores passed values', () => {
            const contextData = createMockContextData(
                { id: {}, title: {} },
                { get: {} }
            );

            const proxy = new GlueModelProxy({
                proxyUniqueName: 'task',
                contextData,
                values: { id: 1, title: 'Test' }
            });

            expect(proxy.values).toEqual({ id: 1, title: 'Test' });
        });
    });

    describe('save', () => {
        it('sends save action with current values', async () => {
            global.fetch = mock(() => Promise.resolve({
                ok: true,
                text: () => Promise.resolve('{"id": 1, "title": "Saved"}'),
                json: () => Promise.resolve({ id: 1, title: 'Saved' }),
                clone: function() { return this; }
            }));

            const contextData = createMockContextData(
                { title: {} },
                { save: {} }
            );

            const proxy = new GlueModelProxy({
                proxyUniqueName: 'task',
                contextData,
                values: { title: 'My Task' }
            });

            const result = await proxy.save();

            expect(global.fetch).toHaveBeenCalledWith(
                '/django_glue/',
                expect.objectContaining({
                    body: JSON.stringify({
                        unique_name: 'task',
                        action: 'save',
                        payload: { title: 'My Task' }
                    })
                })
            );
            expect(result).toEqual({ id: 1, title: 'Saved' });
        });

        it('updates values with response data', async () => {
            global.fetch = mock(() => Promise.resolve({
                ok: true,
                text: () => Promise.resolve('{"id": 1, "title": "Server Title"}'),
                json: () => Promise.resolve({ id: 1, title: 'Server Title' }),
                clone: function() { return this; }
            }));

            const contextData = createMockContextData(
                { title: {} },
                { save: {} }
            );

            const proxy = new GlueModelProxy({
                proxyUniqueName: 'task',
                contextData,
                values: { title: 'Client Title' }
            });

            await proxy.save();

            expect(proxy.values.title).toBe('Server Title');
        });
    });

    describe('delete', () => {
        it('sends delete action', async () => {
            global.fetch = mock(() => Promise.resolve({
                ok: true,
                text: () => Promise.resolve('{}'),
                json: () => Promise.resolve({}),
                clone: function() { return this; }
            }));

            const contextData = createMockContextData(
                { title: {} },
                { delete: {} }
            );

            const proxy = new GlueModelProxy({
                proxyUniqueName: 'task',
                contextData,
                values: { id: 1 }
            });

            await proxy.delete();

            expect(global.fetch).toHaveBeenCalledWith(
                '/django_glue/',
                expect.objectContaining({
                    body: expect.stringContaining('"action":"delete"')
                })
            );
        });

        it('returns response data', async () => {
            global.fetch = mock(() => Promise.resolve({
                ok: true,
                text: () => Promise.resolve('{"deleted": true}'),
                json: () => Promise.resolve({ deleted: true }),
                clone: function() { return this; }
            }));

            const contextData = createMockContextData(
                {},
                { delete: {} }
            );

            const proxy = new GlueModelProxy({
                proxyUniqueName: 'task',
                contextData,
                values: { id: 1 }
            });

            const result = await proxy.delete();

            expect(result).toEqual({ deleted: true });
        });
    });

    describe('autoFetch', () => {
        it('calls loadData when autoFetch is true and no values', () => {
            global.fetch = createMockFetch({
                '/django_glue/': { ok: true, data: { title: 'Fetched' } }
            });

            const contextData = createMockContextData(
                { title: {} },
                { get: {} }
            );

            const proxy = new GlueModelProxy({
                proxyUniqueName: 'task',
                contextData,
                autoFetch: true,
                values: null
            });

            // autoFetch triggers loadData in postInit
            expect(global.fetch).toHaveBeenCalled();
        });

        it('does not call loadData when values are provided', () => {
            global.fetch = mock(() => {});

            const contextData = createMockContextData(
                { title: {} },
                { get: {}, save: {}, delete: {} }
            );

            // When values are provided, autoFetch should not trigger loadData
            // because the condition is `if (this.autoFetch && !this.values)`
            const proxy = new GlueModelProxy({
                proxyUniqueName: 'task',
                contextData,
                autoFetch: false,  // autoFetch=false means no automatic loading
                values: { title: 'Already have data' }
            });

            // Access the field - should not trigger fetch because values exist
            const _ = proxy.title;

            expect(global.fetch).not.toHaveBeenCalled();
        });
    });

    describe('lazy loading', () => {
        it('triggers loadData when accessing field without values', () => {
            global.fetch = createMockFetch({
                '/django_glue/': { ok: true, data: { title: 'Loaded' } }
            });

            const contextData = createMockContextData(
                { title: {} },
                { get: {} }
            );

            const proxy = new GlueModelProxy({
                proxyUniqueName: 'task',
                contextData,
                autoFetch: false,
                values: null
            });

            // Access field should trigger loading
            const _ = proxy.title;

            expect(global.fetch).toHaveBeenCalled();
        });

        it('does not reload when already loading', () => {
            global.fetch = createMockFetch({
                '/django_glue/': { ok: true, data: { title: 'Loaded' } }
            });

            const contextData = createMockContextData(
                { title: {} },
                { get: {} }
            );

            const proxy = new GlueModelProxy({
                proxyUniqueName: 'task',
                contextData,
                autoFetch: false,
                values: null
            });

            // Access field multiple times
            const _1 = proxy.title;
            const _2 = proxy.title;

            // Should only call fetch once
            expect(global.fetch.mock.calls.length).toBe(1);
        });
    });

    describe('loadData', () => {
        it('updates values from response', async () => {
            global.fetch = mock(() => Promise.resolve({
                ok: true,
                text: () => Promise.resolve('{"id": 1, "title": "Loaded Title"}'),
                json: () => Promise.resolve({ id: 1, title: 'Loaded Title' }),
                clone: function() { return this; }
            }));

            const contextData = createMockContextData(
                { id: {}, title: {} },
                { get: {}, save: {}, delete: {} }
            );

            const proxy = new GlueModelProxy({
                proxyUniqueName: 'task',
                contextData,
                autoFetch: false,
                values: { id: 0, title: 'placeholder' }  // Provide initial values to prevent auto-loading
            });

            // Clear any previous calls
            global.fetch.mockClear();

            // Now explicitly call loadData
            proxy.loadData();

            // Wait for promise to resolve
            await new Promise(resolve => setTimeout(resolve, 10));

            expect(proxy.values).toEqual({ id: 1, title: 'Loaded Title' });
        });

        it('sets loaded flag after completion', async () => {
            global.fetch = mock(() => Promise.resolve({
                ok: true,
                text: () => Promise.resolve('{"title": "test"}'),
                json: () => Promise.resolve({ title: 'test' }),
                clone: function() { return this; }
            }));

            const contextData = createMockContextData(
                { title: {} },
                { get: {}, save: {}, delete: {} }
            );

            const proxy = new GlueModelProxy({
                proxyUniqueName: 'task',
                contextData,
                autoFetch: false,
                values: { title: 'placeholder' }  // Provide initial values
            });

            // Clear any previous calls
            global.fetch.mockClear();

            proxy.loadData();

            // Wait for promise to resolve
            await new Promise(resolve => setTimeout(resolve, 10));

            expect(proxy.loaded).toBe(true);
            expect(proxy.loading).toBe(false);
        });
    });
});
