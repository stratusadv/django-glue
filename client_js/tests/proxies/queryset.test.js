import { describe, it, expect, beforeEach, afterEach, mock } from 'bun:test';
import GlueQuerySetProxy from '../../src/proxies/queryset';
import GlueClient from '../../src/client';
import { createMockContextData, setupCookieMock } from '../testUtils';

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

    describe('queryWithParams', () => {
        it('returns array of GlueModelProxy instances', async () => {
            const mockHttp = {
                sendActionRequest: mock(() => Promise.resolve({
                    data: [{ id: 1, title: 'Task 1' }, { id: 2, title: 'Task 2' }]
                }))
            };

            const contextData = createMockContextData(
                { id: {}, title: {} },
                { query_with_params: {} }
            );

            const proxy = new GlueQuerySetProxy({
                http: mockHttp,
                proxyUniqueName: 'tasks',
                contextData
            });

            const items = await proxy.queryWithParams();

            expect(items).toHaveLength(2);
            expect(items[0].title).toBe('Task 1');
            expect(items[1].title).toBe('Task 2');
        });

        it('stores items in _items', async () => {
            const mockHttp = {
                sendActionRequest: mock(() => Promise.resolve({
                    data: [{ id: 1 }]
                }))
            };

            const contextData = createMockContextData(
                { id: {} },
                { query_with_params: {} }
            );

            const proxy = new GlueQuerySetProxy({
                http: mockHttp,
                proxyUniqueName: 'tasks',
                contextData
            });

            await proxy.queryWithParams();

            expect(proxy._items).toHaveLength(1);
        });

        it('returns items with correct uniqueName', async () => {
            const mockHttp = {
                sendActionRequest: mock(() => Promise.resolve({
                    data: [{ id: 1 }]
                }))
            };

            const contextData = createMockContextData(
                { id: {} },
                { query_with_params: {} }
            );

            const proxy = new GlueQuerySetProxy({
                http: mockHttp,
                proxyUniqueName: 'tasks',
                contextData
            });

            const items = await proxy.queryWithParams();

            expect(items[0]._uniqueName).toBe('tasks');
        });

        it('caches results and does not refetch with same params', async () => {
            let callCount = 0;
            const mockHttp = {
                sendActionRequest: mock(() => {
                    callCount++;
                    return Promise.resolve({
                        data: [{ id: 1 }]
                    });
                })
            };

            const contextData = createMockContextData(
                { id: {} },
                { query_with_params: {} }
            );

            const proxy = new GlueQuerySetProxy({
                http: mockHttp,
                proxyUniqueName: 'tasks',
                contextData
            });

            await proxy.queryWithParams({ filter: { done: false } });
            await proxy.queryWithParams({ filter: { done: false } });

            expect(callCount).toBe(1);
        });

        it('refetches when params change', async () => {
            let callCount = 0;
            const mockHttp = {
                sendActionRequest: mock(() => {
                    callCount++;
                    return Promise.resolve({
                        data: [{ id: 1 }]
                    });
                })
            };

            const contextData = createMockContextData(
                { id: {} },
                { query_with_params: {} }
            );

            const proxy = new GlueQuerySetProxy({
                http: mockHttp,
                proxyUniqueName: 'tasks',
                contextData
            });

            await proxy.queryWithParams({ filter: { done: false } });
            await proxy.queryWithParams({ filter: { done: true } });

            expect(callCount).toBe(2);
        });
    });

    describe('all', () => {
        it('calls queryWithParams with no params', async () => {
            const mockHttp = {
                sendActionRequest: mock(() => Promise.resolve({
                    data: [{ id: 1 }]
                }))
            };

            const contextData = createMockContextData(
                { id: {} },
                { query_with_params: {} }
            );

            const proxy = new GlueQuerySetProxy({
                http: mockHttp,
                proxyUniqueName: 'tasks',
                contextData
            });

            const items = await proxy.all();

            expect(items).toHaveLength(1);
        });
    });

    describe('filter', () => {
        it('adds filter query param and returns proxy', async () => {
            const mockHttp = {
                sendActionRequest: mock(() => Promise.resolve({
                    data: [{ id: 1, done: false }]
                }))
            };

            const contextData = createMockContextData(
                { id: {}, done: {} },
                { query_with_params: {} }
            );

            const proxy = new GlueQuerySetProxy({
                http: mockHttp,
                proxyUniqueName: 'tasks',
                contextData
            });

            const result = proxy.filter({ done: false });

            expect(result).toBe(proxy);
            expect(proxy._queryParams.filter).toEqual({ done: false });
        });

        it('supports Django ORM lookups', async () => {
            const mockHttp = {
                sendActionRequest: mock(() => Promise.resolve({
                    data: [{ id: 1, title: 'urgent task' }]
                }))
            };

            const contextData = createMockContextData(
                { id: {}, title: {} },
                { query_with_params: {} }
            );

            const proxy = new GlueQuerySetProxy({
                http: mockHttp,
                proxyUniqueName: 'tasks',
                contextData
            });

            proxy.filter({ title__icontains: 'urgent' });

            expect(proxy._queryParams.filter).toEqual({ title__icontains: 'urgent' });
        });
    });

    describe('orderBy', () => {
        it('adds order_by query param and returns proxy', () => {
            const mockHttp = {
                sendActionRequest: mock(() => Promise.resolve({ data: [] }))
            };

            const contextData = createMockContextData(
                { id: {} },
                { query_with_params: {} }
            );

            const proxy = new GlueQuerySetProxy({
                http: mockHttp,
                proxyUniqueName: 'tasks',
                contextData
            });

            const result = proxy.orderBy({ title: 'asc' });

            expect(result).toBe(proxy);
            expect(proxy._queryParams.order_by).toEqual({ title: 'asc' });
        });
    });

    describe('slice', () => {
        it('adds slice query param', () => {
            const mockHttp = {
                sendActionRequest: mock(() => Promise.resolve({ data: [] }))
            };

            const contextData = createMockContextData(
                { id: {} },
                { query_with_params: {} }
            );

            const proxy = new GlueQuerySetProxy({
                http: mockHttp,
                proxyUniqueName: 'tasks',
                contextData
            });

            proxy.slice(0, 10);

            expect(proxy._queryParams.slice).toEqual({ start: 0, stop: 10 });
        });

        it('sliceStart adds start param', () => {
            const mockHttp = {
                sendActionRequest: mock(() => Promise.resolve({ data: [] }))
            };

            const contextData = createMockContextData(
                { id: {} },
                { query_with_params: {} }
            );

            const proxy = new GlueQuerySetProxy({
                http: mockHttp,
                proxyUniqueName: 'tasks',
                contextData
            });

            proxy.sliceStart(5);

            expect(proxy._queryParams.slice).toEqual({ start: 5 });
        });

        it('sliceEnd adds stop param', () => {
            const mockHttp = {
                sendActionRequest: mock(() => Promise.resolve({ data: [] }))
            };

            const contextData = createMockContextData(
                { id: {} },
                { query_with_params: {} }
            );

            const proxy = new GlueQuerySetProxy({
                http: mockHttp,
                proxyUniqueName: 'tasks',
                contextData
            });

            proxy.sliceEnd(10);

            expect(proxy._queryParams.slice).toEqual({ stop: 10 });
        });
    });

    describe('iterator', () => {
        it('supports for...of iteration', async () => {
            const mockHttp = {
                sendActionRequest: mock(() => Promise.resolve({
                    data: [{ id: 1 }, { id: 2 }]
                }))
            };

            const contextData = createMockContextData(
                { id: {} },
                { query_with_params: {} }
            );

            const proxy = new GlueQuerySetProxy({
                http: mockHttp,
                proxyUniqueName: 'tasks',
                contextData
            });

            await proxy.queryWithParams();

            const ids = [];
            for (const item of proxy) {
                ids.push(item._values.id);
            }

            expect(ids).toEqual([1, 2]);
        });

        it('supports spread operator', async () => {
            const mockHttp = {
                sendActionRequest: mock(() => Promise.resolve({
                    data: [{ id: 1 }, { id: 2 }, { id: 3 }]
                }))
            };

            const contextData = createMockContextData(
                { id: {} },
                { query_with_params: {} }
            );

            const proxy = new GlueQuerySetProxy({
                http: mockHttp,
                proxyUniqueName: 'tasks',
                contextData
            });

            await proxy.queryWithParams();

            const items = [...proxy];

            expect(items).toHaveLength(3);
        });
    });

    describe('refresh', () => {
        it('clears items and reloads', async () => {
            let callCount = 0;
            const mockHttp = {
                sendActionRequest: mock(() => {
                    callCount++;
                    return Promise.resolve({
                        data: [{ id: callCount }]
                    });
                })
            };

            const contextData = createMockContextData(
                { id: {} },
                { query_with_params: {} }
            );

            const proxy = new GlueQuerySetProxy({
                http: mockHttp,
                proxyUniqueName: 'tasks',
                contextData
            });

            await proxy.queryWithParams();
            expect(proxy._items).toHaveLength(1);
            expect(proxy._items[0]._values.id).toBe(1);

            await proxy.refresh();
            expect(proxy._items).toHaveLength(1);
            expect(proxy._items[0]._values.id).toBe(2);
        });
    });

    describe('isEmpty and isLoaded', () => {
        it('isEmpty is false before loading', () => {
            const mockHttp = {
                sendActionRequest: mock(() => Promise.resolve({ data: [] }))
            };

            const contextData = createMockContextData(
                { id: {} },
                { query_with_params: {} }
            );

            const proxy = new GlueQuerySetProxy({
                http: mockHttp,
                proxyUniqueName: 'tasks',
                contextData
            });

            expect(proxy.isEmpty).toBe(false);
            expect(proxy.isLoaded).toBe(false);
        });

        it('isEmpty is true after loading empty results', async () => {
            const mockHttp = {
                sendActionRequest: mock(() => Promise.resolve({ data: [] }))
            };

            const contextData = createMockContextData(
                { id: {} },
                { query_with_params: {} }
            );

            const proxy = new GlueQuerySetProxy({
                http: mockHttp,
                proxyUniqueName: 'tasks',
                contextData
            });

            await proxy.queryWithParams();

            expect(proxy.isEmpty).toBe(true);
            expect(proxy.isLoaded).toBe(true);
        });
    });

    describe('pushNew', () => {
        it('prepends new item by default', async () => {
            const mockHttp = {
                sendActionRequest: mock(() => Promise.resolve({
                    data: { id: 0, title: 'New' }
                }))
            };

            const contextData = createMockContextData(
                { id: {}, title: {} },
                { new: {} }
            );

            const proxy = new GlueQuerySetProxy({
                http: mockHttp,
                proxyUniqueName: 'tasks',
                contextData
            });

            const items = await proxy.pushNew();

            expect(items).toHaveLength(1);
            expect(items[0]._values.title).toBe('New');
        });

        it('appends new item when location is end', async () => {
            const mockHttp = {
                sendActionRequest: mock(() => Promise.resolve({
                    data: { id: 0, title: 'New' }
                }))
            };

            const contextData = createMockContextData(
                { id: {}, title: {} },
                { new: {} }
            );

            const proxy = new GlueQuerySetProxy({
                http: mockHttp,
                proxyUniqueName: 'tasks',
                contextData
            });

            const items = await proxy.pushNew('end');

            expect(items).toHaveLength(1);
        });

        it('throws on invalid location', async () => {
            const mockHttp = {
                sendActionRequest: mock(() => Promise.resolve({
                    data: { id: 0 }
                }))
            };

            const contextData = createMockContextData(
                { id: {} },
                { new: {} }
            );

            const proxy = new GlueQuerySetProxy({
                http: mockHttp,
                proxyUniqueName: 'tasks',
                contextData
            });

            await expect(proxy.pushNew('invalid')).rejects.toThrow('Invalid location');
        });
    });

    describe('prependNew and appendNew', () => {
        it('prependNew calls pushNew with start', async () => {
            const mockHttp = {
                sendActionRequest: mock(() => Promise.resolve({
                    data: { id: 0 }
                }))
            };

            const contextData = createMockContextData(
                { id: {} },
                { new: {} }
            );

            const proxy = new GlueQuerySetProxy({
                http: mockHttp,
                proxyUniqueName: 'tasks',
                contextData
            });

            const items = await proxy.prependNew();
            expect(items).toHaveLength(1);
        });

        it('appendNew calls pushNew with end', async () => {
            const mockHttp = {
                sendActionRequest: mock(() => Promise.resolve({
                    data: { id: 0 }
                }))
            };

            const contextData = createMockContextData(
                { id: {} },
                { new: {} }
            );

            const proxy = new GlueQuerySetProxy({
                http: mockHttp,
                proxyUniqueName: 'tasks',
                contextData
            });

            const items = await proxy.appendNew();
            expect(items).toHaveLength(1);
        });
    });
});
