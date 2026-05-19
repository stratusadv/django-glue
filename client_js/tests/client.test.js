import { describe, it, expect, beforeEach, afterEach, mock } from 'bun:test';
import GlueClient from '../src/client';
import { setupCookieMock } from './testUtils';

describe('GlueClient', () => {
    let client;
    let originalSetInterval;
    let originalClearInterval;

    beforeEach(() => {
        originalSetInterval = global.setInterval;
        originalClearInterval = global.clearInterval;
        client = new GlueClient();

        // Mock setInterval for keep-alive
        global.setInterval = mock(() => 123);
        global.clearInterval = mock(() => {});
        setupCookieMock({ csrftoken: 'test-token' });
    });

    afterEach(() => {
        global.setInterval = originalSetInterval;
        global.clearInterval = originalClearInterval;
        GlueClient.contextData = {};
        GlueClient.proxyRegistry = {};
    });

    describe('init', () => {
        it('creates http instance with config', () => {
            const config = {
                requestTimeoutSeconds: 60,
                actionUrlPath: '/__dg__/action/',
                keepLiveUrlPath: '/__dg__/keep_live/',
                glueViewUrlPath: '/__dg__/glue_view/',
            };

            client.init({
                proxyRegistryFromSession: {},
                contextDataForProxies: {},
                config
            });

            expect(client.http).toBeDefined();
            expect(client._config).toBe(config);
        });

        it('defines proxy properties from contextData', () => {
            const config = {
                actionUrlPath: '/__dg__/action/',
                keepLiveUrlPath: '/__dg__/keep_live/',
                glueViewUrlPath: '/__dg__/glue_view/',
            };

            const contextData = {
                'task': {
                    subject_type: 'Model',
                    fields: { id: {}, title: {} },
                    actions: { get: {}, save: {}, delete: {} },
                    initial: {}
                },
                'tasks': {
                    subject_type: 'QuerySet',
                    fields: { id: {} },
                    actions: { query_with_params: {} },
                    initial: {}
                }
            };

            client.init({
                proxyRegistryFromSession: { task: 'view', tasks: 'change' },
                contextDataForProxies: contextData,
                config
            });

            expect(client.model.task).toBeDefined();
            expect(client.querySet.tasks).toBeDefined();
        });

        it('sets static contextData on GlueClient class', () => {
            const config = {
                actionUrlPath: '/__dg__/action/',
                keepLiveUrlPath: '/__dg__/keep_live/',
                glueViewUrlPath: '/__dg__/glue_view/',
            };

            const contextData = {
                'task': {
                    subject_type: 'Model',
                    fields: { id: {} },
                    actions: { get: {} },
                    initial: {}
                }
            };

            client.init({
                proxyRegistryFromSession: { task: 'view' },
                contextDataForProxies: contextData,
                config
            });

            expect(GlueClient.contextData.task).toBeDefined();
        });

        it('sets static proxyRegistry on GlueClient class', () => {
            const config = {
                actionUrlPath: '/__dg__/action/',
                keepLiveUrlPath: '/__dg__/keep_live/',
                glueViewUrlPath: '/__dg__/glue_view/',
            };

            const registry = { task: 'delete', tasks: 'change' };

            client.init({
                proxyRegistryFromSession: registry,
                contextDataForProxies: {},
                config
            });

            expect(GlueClient.proxyRegistry).toEqual(registry);
        });

        it('handles empty registry', () => {
            const config = {
                actionUrlPath: '/__dg__/action/',
                keepLiveUrlPath: '/__dg__/keep_live/',
                glueViewUrlPath: '/__dg__/glue_view/',
            };

            // Should not throw
            client.init({
                proxyRegistryFromSession: {},
                contextDataForProxies: {},
                config
            });
        });

        it('works without config parameter', () => {
            // Should not throw
            client.init({
                proxyRegistryFromSession: {},
                contextDataForProxies: {},
            });
        });
    });

    describe('proxy type creation', () => {
        it('creates GlueModelProxy for Model subject type', () => {
            const config = {
                actionUrlPath: '/__dg__/action/',
                keepLiveUrlPath: '/__dg__/keep_live/',
                glueViewUrlPath: '/__dg__/glue_view/',
            };

            const contextData = {
                'task': {
                    subject_type: 'Model',
                    fields: { id: {}, title: {} },
                    actions: { get: {}, save: {}, delete: {} },
                    initial: {}
                }
            };

            client.init({
                proxyRegistryFromSession: { task: 'view' },
                contextDataForProxies: contextData,
                config
            });

            // Model proxy should have save and delete methods
            expect(typeof client.model.task.save).toBe('function');
            expect(typeof client.model.task.delete).toBe('function');
        });

        it('creates GlueQuerySetProxy for QuerySet subject type', () => {
            const config = {
                actionUrlPath: '/__dg__/action/',
                keepLiveUrlPath: '/__dg__/keep_live/',
                glueViewUrlPath: '/__dg__/glue_view/',
            };

            const contextData = {
                'tasks': {
                    subject_type: 'QuerySet',
                    fields: { id: {}, title: {} },
                    actions: { query_with_params: {} },
                    initial: {}
                }
            };

            client.init({
                proxyRegistryFromSession: { tasks: 'change' },
                contextDataForProxies: contextData,
                config
            });

            // QuerySet proxy should have queryWithParams and filter methods
            expect(typeof client.querySet.tasks.queryWithParams).toBe('function');
            expect(typeof client.querySet.tasks.filter).toBe('function');
        });

        it('creates GlueFormProxy for BaseForm subject type', () => {
            const config = {
                actionUrlPath: '/__dg__/action/',
                keepLiveUrlPath: '/__dg__/keep_live/',
                glueViewUrlPath: '/__dg__/glue_view/',
            };

            const contextData = {
                'contact_form': {
                    subject_type: 'BaseForm',
                    fields: { name: {}, email: {} },
                    initial: {},
                    actions: { get: {}, validate: {}, save: {} }
                }
            };

            client.init({
                proxyRegistryFromSession: { contact_form: 'change' },
                contextDataForProxies: contextData,
                config
            });

            // Form proxy should have validate and save methods
            expect(typeof client.form.contact_form.validate).toBe('function');
            expect(typeof client.form.contact_form.save).toBe('function');
        });
    });

    describe('initializeProxies', () => {
        it('can be called independently to add more proxies', () => {
            const config = {
                actionUrlPath: '/__dg__/action/',
                keepLiveUrlPath: '/__dg__/keep_live/',
                glueViewUrlPath: '/__dg__/glue_view/',
            };

            client._config = config;
            client.http = { sendKeepLiveRequest: () => Promise.resolve({ ok: true }) };

            const contextData = {
                'task': {
                    subject_type: 'Model',
                    fields: { id: {} },
                    actions: { get: {} },
                    initial: {}
                }
            };

            client.initializeProxies({ task: 'view' }, contextData);

            expect(client.model.task).toBeDefined();
            expect(GlueClient.contextData.task).toBeDefined();
        });
    });

    describe('view', () => {
        it('returns a GlueView instance', () => {
            const config = {
                actionUrlPath: '/__dg__/action/',
                keepLiveUrlPath: '/__dg__/keep_live/',
                glueViewUrlPath: '/__dg__/glue_view/',
            };

            // Mock window.location for GlueView constructor
            Object.defineProperty(window, 'location', {
                value: { origin: 'http://localhost:3000', pathname: '/' },
                writable: true,
                configurable: true
            });

            client.init({
                proxyRegistryFromSession: {},
                contextDataForProxies: {},
                config
            });

            const view = client.view('/some/url/', { shared: 'data' });

            expect(view).toBeDefined();
            expect(view.url).toBe('/some/url/');
            expect(view.shared_payload).toEqual({ shared: 'data' });
        });
    });

    describe('fetch', () => {
        it('delegates to http.sendRequest', async () => {
            const config = {
                actionUrlPath: '/__dg__/action/',
                keepLiveUrlPath: '/__dg__/keep_live/',
                glueViewUrlPath: '/__dg__/glue_view/',
            };

            client._config = config;
            const sendRequestSpy = mock(() => Promise.resolve({ data: { result: 'ok' } }));
            client.http = { sendRequest: sendRequestSpy };

            const result = await client.fetch('/test', { method: 'GET' });

            expect(sendRequestSpy).toHaveBeenCalledWith('/test', { method: 'GET' });
            expect(result).toEqual({ data: { result: 'ok' } });
        });
    });
});
