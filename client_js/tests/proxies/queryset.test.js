import { describe, it, expect, beforeEach, afterEach, mock } from 'bun:test';
import { GlueQuerySetProxy } from '../../src/proxies/queryset';
import GlueClient from '../../src/client';
import { createMockFetch, createMockContextData, setupCookieMock } from '../testUtils';

mock.module('../../src/constants', () => ({
    actionUrl: '/django_glue/',
    keepLiveUrl: '/django_glue/keep_live/'
}));

describe('GlueQuerySetProxy', () => {
    let originalFetch;

    beforeEach(() => {
        originalFetch = global.fetch;
        setupCookieMock({ csrftoken: 'test-token' });

        // Set up GlueClient.contextData for queryset item building
        GlueClient.contextData = {
            'tasks': {
                fields: { id: {}, title: {}, done: {} },
                actions: { save: {}, delete: {} }
            }
        };
    });

    afterEach(() => {
        global.fetch = originalFetch;
        GlueClient.contextData = {};
    });

    describe('all', () => {
        it('returns array of GlueModelProxy instances', async () => {
            global.fetch = mock(() => Promise.resolve({
                ok: true,
                text: () => Promise.resolve('[{"id": 1, "title": "Task 1"}, {"id": 2, "title": "Task 2"}]'),
                json: () => Promise.resolve([{ id: 1, title: 'Task 1' }, { id: 2, title: 'Task 2' }]),
                clone: function() { return this; }
            }));

            const contextData = createMockContextData(
                { id: {}, title: {} },
                { all: {}, filter: {}, save: {}, delete: {} }
            );

            const proxy = new GlueQuerySetProxy({
                proxyUniqueName: 'tasks',
                contextData
            });

            const items = await proxy.queryWithParams();

            expect(items).toHaveLength(2);
            expect(items[0].title).toBe('Task 1');
            expect(items[1].title).toBe('Task 2');
        });

        it('stores items in proxy.items', async () => {
            global.fetch = mock(() => Promise.resolve({
                ok: true,
                text: () => Promise.resolve('[{"id": 1}]'),
                json: () => Promise.resolve([{ id: 1 }]),
                clone: function() { return this; }
            }));

            const contextData = createMockContextData(
                { id: {} },
                { all: {}, filter: {} }
            );

            const proxy = new GlueQuerySetProxy({
                proxyUniqueName: 'tasks',
                contextData
            });

            await proxy.queryWithParams();

            expect(proxy.items).toHaveLength(1);
        });

        it('returns items with correct uniqueName', async () => {
            global.fetch = mock(() => Promise.resolve({
                ok: true,
                text: () => Promise.resolve('[{"id": 1}]'),
                json: () => Promise.resolve([{ id: 1 }]),
                clone: function() { return this; }
            }));

            const contextData = createMockContextData(
                { id: {} },
                { all: {}, filter: {} }
            );

            const proxy = new GlueQuerySetProxy({
                proxyUniqueName: 'tasks',
                contextData
            });

            const items = await proxy.queryWithParams();

            expect(items[0].uniqueName).toBe('tasks');
        });

        it('returns items with save and delete actions pre-configured', async () => {
            global.fetch = mock(() => Promise.resolve({
                ok: true,
                text: () => Promise.resolve('[{"id": 42}]'),
                json: () => Promise.resolve([{ id: 42 }]),
                clone: function() { return this; }
            }));

            const contextData = createMockContextData(
                { id: {} },
                { all: {}, filter: {} }
            );

            const proxy = new GlueQuerySetProxy({
                proxyUniqueName: 'tasks',
                contextData
            });

            const items = await proxy.queryWithParams();

            expect(items[0].actions.save.payload).toEqual({ id: 42 });
            expect(items[0].actions.delete.payload).toEqual({ id: 42 });
        });
    });

    describe('filter', () => {
        it('sends filter params to server', async () => {
            global.fetch = mock(() => Promise.resolve({
                ok: true,
                text: () => Promise.resolve('[{"id": 1, "done": false}]'),
                json: () => Promise.resolve([{ id: 1, done: false }]),
                clone: function() { return this; }
            }));

            const contextData = createMockContextData(
                { id: {}, done: {} },
                { all: {}, filter: {} }
            );

            const proxy = new GlueQuerySetProxy({
                proxyUniqueName: 'tasks',
                contextData
            });

            await proxy.filter({ done: false });

            expect(global.fetch).toHaveBeenCalledWith(
                '/django_glue/',
                expect.objectContaining({
                    body: expect.stringContaining('"payload":{"done":false}')
                })
            );
        });

        it('returns filtered items as GlueModelProxy instances', async () => {
            global.fetch = mock(() => Promise.resolve({
                ok: true,
                text: () => Promise.resolve('[{"id": 1, "done": false}, {"id": 3, "done": false}]'),
                json: () => Promise.resolve([{ id: 1, done: false }, { id: 3, done: false }]),
                clone: function() { return this; }
            }));

            const contextData = createMockContextData(
                { id: {}, done: {} },
                { all: {}, filter: {} }
            );

            const proxy = new GlueQuerySetProxy({
                proxyUniqueName: 'tasks',
                contextData
            });

            const items = await proxy.filter({ done: false });

            expect(items).toHaveLength(2);
            expect(items[0].done).toBe(false);
            expect(items[1].done).toBe(false);
        });

        it('updates proxy.items with filtered results', async () => {
            global.fetch = mock(() => Promise.resolve({
                ok: true,
                text: () => Promise.resolve('[{"id": 1}]'),
                json: () => Promise.resolve([{ id: 1 }]),
                clone: function() { return this; }
            }));

            const contextData = createMockContextData(
                { id: {} },
                { all: {}, filter: {} }
            );

            const proxy = new GlueQuerySetProxy({
                proxyUniqueName: 'tasks',
                contextData
            });

            await proxy.filter({ done: true });

            expect(proxy.items).toHaveLength(1);
        });

        it('supports Django ORM lookups', async () => {
            global.fetch = mock(() => Promise.resolve({
                ok: true,
                text: () => Promise.resolve('[]'),
                json: () => Promise.resolve([]),
                clone: function() { return this; }
            }));

            const contextData = createMockContextData(
                { id: {}, title: {} },
                { all: {}, filter: {} }
            );

            const proxy = new GlueQuerySetProxy({
                proxyUniqueName: 'tasks',
                contextData
            });

            await proxy.filter({ title__icontains: 'urgent' });

            expect(global.fetch).toHaveBeenCalledWith(
                '/django_glue/',
                expect.objectContaining({
                    body: expect.stringContaining('"title__icontains":"urgent"')
                })
            );
        });
    });

    describe('iterator', () => {
        it('supports for...of iteration', async () => {
            global.fetch = mock(() => Promise.resolve({
                ok: true,
                text: () => Promise.resolve('[{"id": 1}, {"id": 2}]'),
                json: () => Promise.resolve([{ id: 1 }, { id: 2 }]),
                clone: function() { return this; }
            }));

            const contextData = createMockContextData(
                { id: {} },
                { all: {}, filter: {} }
            );

            const proxy = new GlueQuerySetProxy({
                proxyUniqueName: 'tasks',
                contextData
            });

            await proxy.queryWithParams();

            const ids = [];
            for (const item of proxy) {
                ids.push(item.values.id);
            }

            expect(ids).toEqual([1, 2]);
        });

        it('supports spread operator', async () => {
            global.fetch = mock(() => Promise.resolve({
                ok: true,
                text: () => Promise.resolve('[{"id": 1}, {"id": 2}, {"id": 3}]'),
                json: () => Promise.resolve([{ id: 1 }, { id: 2 }, { id: 3 }]),
                clone: function() { return this; }
            }));

            const contextData = createMockContextData(
                { id: {} },
                { all: {}, filter: {} }
            );

            const proxy = new GlueQuerySetProxy({
                proxyUniqueName: 'tasks',
                contextData
            });

            await proxy.queryWithParams();

            const items = [...proxy];

            expect(items).toHaveLength(3);
        });
    });

    describe('buildQuerySetItem', () => {
        it('creates GlueModelProxy with copied values', async () => {
            global.fetch = mock(() => Promise.resolve({
                ok: true,
                text: () => Promise.resolve('[{"id": 1, "title": "Original"}]'),
                json: () => Promise.resolve([{ id: 1, title: 'Original' }]),
                clone: function() { return this; }
            }));

            const contextData = createMockContextData(
                { id: {}, title: {} },
                { all: {}, filter: {} }
            );

            const proxy = new GlueQuerySetProxy({
                proxyUniqueName: 'tasks',
                contextData
            });

            const items = await proxy.queryWithParams();

            // Modifying returned item should not affect internal data
            items[0].title = 'Modified';

            expect(items[0].title).toBe('Modified');
        });

        it('uses contextData from GlueClient', async () => {
            GlueClient.contextData = {
                'tasks': {
                    fields: { id: {}, title: {}, custom: {} },
                    actions: { save: {}, delete: {}, custom: {} }
                }
            };

            global.fetch = mock(() => Promise.resolve({
                ok: true,
                text: () => Promise.resolve('[{"id": 1}]'),
                json: () => Promise.resolve([{ id: 1 }]),
                clone: function() { return this; }
            }));

            const contextData = createMockContextData(
                { id: {} },
                { all: {}, filter: {} }
            );

            const proxy = new GlueQuerySetProxy({
                proxyUniqueName: 'tasks',
                contextData
            });

            const items = await proxy.queryWithParams();

            // Should have access to custom field from GlueClient.contextData
            expect(items[0].contextData.fields.custom).toBeDefined();
        });
    });
});
