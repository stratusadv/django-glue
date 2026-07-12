import {afterEach, beforeEach, describe, expect, it, mock} from 'bun:test';
import GlueClient from '../src/client';
import GlueHttp from '../src/http';
import GlueFormProxy from '../src/proxies/form';
import GlueModelProxy from '../src/proxies/model';
import GlueQuerySetProxy from '../src/proxies/queryset';
import GlueView from '../src/view';
import {
    createFormPolicy,
    createFunctionPolicy,
    createModelPolicy,
    createQuerySetPolicy,
    createState,
} from './testUtils';

describe('GlueClient', () => {
    let client;
    let originalLocation;
    const config = {
        requestTimeoutSeconds: 30,
        attributeEventUrlPath: '/__dg__/bound_attribute_event/',
        glueViewUrlPath: '/__dg__/glue_view/',
    };

    beforeEach(() => {
        client = new GlueClient();
        originalLocation = window.location;
        Object.defineProperty(window, 'location', {
            value: {origin: 'http://localhost:3000', pathname: '/current/page'},
            writable: true,
            configurable: true,
        });
    });

    afterEach(() => {
        Object.defineProperty(window, 'location', {
            value: originalLocation,
            writable: true,
            configurable: true,
        });
    });

    it('initializes an HTTP client with config', () => {
        client.init({proxies: {}, config});

        expect(client._config).toBe(config);
        expect(client.http).toBeInstanceOf(GlueHttp);
    });

    it('registers form, model, and queryset proxies by namespace', () => {
        client.init({
            config,
            proxies: {
                contact: {
                    policy: createFormPolicy(),
                    state: createState({name: 'Ada'}),
                },
                gorilla: {
                    policy: createModelPolicy(),
                    state: createState({id: 1, name: 'Koko'}),
                },
                gorillas: {
                    policy: createQuerySetPolicy(),
                    state: {list_data: []},
                },
            },
        });

        expect(client.form.contact).toBeInstanceOf(GlueFormProxy);
        expect(client.model.gorilla).toBeInstanceOf(GlueModelProxy);
        expect(client.querySet.gorillas).toBeInstanceOf(GlueQuerySetProxy);
    });

    it('registers function proxies as callable functions', async () => {
        client.init({
            config,
            proxies: {
                calculate: {
                    policy: createFunctionPolicy(),
                    state: null,
                },
            },
        });

        expect(typeof client.function.calculate).toBe('function');
    });

    it('delegates fetch to GlueHttp', async () => {
        client.init({proxies: {}, config});
        client.http.sendRequest = mock(async () => ({data: {ok: true}}));

        const response = await client.fetch('/url/', {method: 'GET'});

        expect(response.data.ok).toBe(true);
        expect(client.http.sendRequest).toHaveBeenCalledWith('/url/', {method: 'GET'});
    });

    it('creates GlueView instances with the current HTTP client', () => {
        client.init({proxies: {}, config});

        const view = client.view('/fragment/', {shared: true});

        expect(view).toBeInstanceOf(GlueView);
        expect(view.http).toBe(client.http);
        expect(view.shared_payload).toEqual({shared: true});
    });
});
