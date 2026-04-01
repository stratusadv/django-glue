import { describe, it, expect, beforeEach, afterEach, mock, spyOn } from 'bun:test';
import GlueClient from '../src/client';
import { resetConfig, getConfig } from '../src/config';
import { createMockFetch, setupCookieMock } from './testUtils';

mock.module('../src/constants', () => ({
    actionUrl: '/django_glue/',
    keepLiveUrl: '/django_glue/keep_live/'
}));

describe('GlueClient', () => {
    let client;
    let originalFetch;
    let originalSetInterval;
    let originalClearInterval;

    beforeEach(() => {
        originalFetch = global.fetch;
        originalSetInterval = global.setInterval;
        originalClearInterval = global.clearInterval;
        client = new GlueClient();
        resetConfig();
        setupCookieMock({ csrftoken: 'test-token' });

        // Mock setInterval for keep-alive
        global.setInterval = mock(() => 123);
        global.clearInterval = mock(() => {});
    });

    afterEach(() => {
        global.fetch = originalFetch;
        global.setInterval = originalSetInterval;
        global.clearInterval = originalClearInterval;
        GlueClient.contextData = {};
    });

    describe('init', () => {
        it('defines proxy properties from registry', () => {
            global.fetch = createMockFetch({});

            const registry = {
                'task': { unique_name: 'task', subject_type: 'Model' },
                'tasks': { unique_name: 'tasks', subject_type: 'QuerySet' }
            };

            const contextData = {
                'task': { fields: { id: {} }, actions: { get: {}, save: {}, delete: {} } },
                'tasks': { fields: { id: {} }, actions: { all: {}, filter: {} } }
            };

            client.init({
                proxyRegistryFromSession: registry,
                contextDataForProxies: contextData,
                keepLiveInterval: 60000
            });

            // Properties should be defined (lazy - not instantiated yet)
            expect(Object.getOwnPropertyDescriptor(client, 'task')).toBeDefined();
            expect(Object.getOwnPropertyDescriptor(client, 'tasks')).toBeDefined();
        });

        it('sets contextData on GlueClient class', () => {
            global.fetch = createMockFetch({});

            const contextData = {
                'task': { fields: { id: {} }, actions: { get: {}, save: {}, delete: {} } }
            };

            client.init({
                proxyRegistryFromSession: { 'task': { unique_name: 'task', subject_type: 'Model' } },
                contextDataForProxies: contextData,
                keepLiveInterval: 60000
            });

            expect(GlueClient.contextData).toBe(contextData);
        });

        it('applies config when provided', () => {
            global.fetch = createMockFetch({});

            client.init({
                proxyRegistryFromSession: {},
                contextDataForProxies: {},
                keepLiveInterval: 60000,
                config: { requestTimeoutMs: 5000 }
            });

            expect(getConfig().requestTimeoutMs).toBe(5000);
        });

        it('works without config parameter', () => {
            global.fetch = createMockFetch({});

            // Should not throw
            client.init({
                proxyRegistryFromSession: {},
                contextDataForProxies: {},
                keepLiveInterval: 60000
            });

            // Default config should be intact
            expect(getConfig().requestTimeoutMs).toBe(30000);
        });

        it('handles empty registry', () => {
            global.fetch = createMockFetch({});

            // Should not throw
            client.init({
                proxyRegistryFromSession: {},
                contextDataForProxies: {},
                keepLiveInterval: 60000
            });
        });
    });

    describe('lazy proxy instantiation', () => {
        it('creates proxy on first access', () => {
            global.fetch = createMockFetch({});

            const contextData = {
                'task': {
                    fields: { id: {}, title: {} },
                    actions: { get: {}, save: {}, delete: {} }
                }
            };

            client.init({
                proxyRegistryFromSession: {
                    'task': { unique_name: 'task', subject_type: 'Model' }
                },
                contextDataForProxies: contextData,
                keepLiveInterval: 60000
            });

            const proxy = client.task;

            expect(proxy.uniqueName).toBe('task');
        });

        it('returns same proxy instance on subsequent access', () => {
            global.fetch = createMockFetch({});

            const contextData = {
                'task': {
                    fields: { id: {} },
                    actions: { get: {}, save: {}, delete: {} }
                }
            };

            client.init({
                proxyRegistryFromSession: {
                    'task': { unique_name: 'task', subject_type: 'Model' }
                },
                contextDataForProxies: contextData,
                keepLiveInterval: 60000
            });

            const proxy1 = client.task;
            const proxy2 = client.task;

            expect(proxy1).toBe(proxy2);
        });

        it('creates correct proxy type for model', () => {
            global.fetch = createMockFetch({});

            const contextData = {
                'task': {
                    fields: { id: {}, title: {} },
                    actions: { get: {}, save: {}, delete: {} }
                }
            };

            client.init({
                proxyRegistryFromSession: {
                    'task': { unique_name: 'task', subject_type: 'Model' }
                },
                contextDataForProxies: contextData,
                keepLiveInterval: 60000
            });

            const proxy = client.task;

            // Model proxy should have save and delete methods
            expect(typeof proxy.save).toBe('function');
            expect(typeof proxy.delete).toBe('function');
        });

        it('creates correct proxy type for queryset', () => {
            global.fetch = createMockFetch({});

            const contextData = {
                'tasks': {
                    fields: { id: {}, title: {} },
                    actions: { all: {}, filter: {} }
                }
            };

            client.init({
                proxyRegistryFromSession: {
                    'tasks': { unique_name: 'tasks', subject_type: 'QuerySet' }
                },
                contextDataForProxies: contextData,
                keepLiveInterval: 60000
            });

            const proxy = client.tasks;

            // QuerySet proxy should have all and filter methods
            expect(typeof proxy.queryWithParams).toBe('function');
            expect(typeof proxy.filter).toBe('function');
        });

        it('creates correct proxy type for form', () => {
            global.fetch = createMockFetch({});

            const contextData = {
                'contact_form': {
                    fields: { name: {}, email: {} },
                    initial: {},
                    actions: { get: {}, validate: {}, submit: {} }
                }
            };

            client.init({
                proxyRegistryFromSession: {
                    'contact_form': { unique_name: 'contact_form', subject_type: 'BaseForm' }
                },
                contextDataForProxies: contextData,
                keepLiveInterval: 60000
            });

            const proxy = client.contact_form;

            // Form proxy should have validate and submit methods
            expect(typeof proxy.validate).toBe('function');
            expect(typeof proxy.submit).toBe('function');
        });
    });

    describe('static contextData', () => {
        it('is shared across instances', () => {
            global.fetch = createMockFetch({});

            const contextData = { shared: 'data' };

            client.init({
                proxyRegistryFromSession: {},
                contextDataForProxies: contextData,
                keepLiveInterval: 60000
            });

            expect(GlueClient.contextData).toBe(contextData);
        });
    });
});
