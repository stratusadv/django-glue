import {afterEach, beforeEach, describe, expect, it, mock} from 'bun:test';
import {GlueHttpError} from '../src/errors';
import GlueHttp from '../src/http';
import {createFormPolicy, setupCookieMock} from './testUtils';

describe('GlueHttp', () => {
    let originalFetch;
    let http;

    beforeEach(() => {
        originalFetch = global.fetch;
        setupCookieMock({csrftoken: 'test-csrf-token'});
        http = new GlueHttp({
            requestTimeoutSeconds: 30,
            attributeEventUrlPath: '/__dg__/bound_attribute_event/',
            glueViewUrlPath: '/__dg__/glue_view/',
        });
    });

    afterEach(() => {
        global.fetch = originalFetch;
    });

    it('reads a cookie by name', () => {
        expect(http.getCookie('csrftoken')).toBe('test-csrf-token');
        expect(http.getCookie('missing')).toBeNull();
    });

    it('sends JSON requests with csrf headers', async () => {
        let capturedOptions;
        global.fetch = mock((url, options) => {
            capturedOptions = options;
            return Promise.resolve({
                ok: true,
                text: () => Promise.resolve('{"ok":true}'),
                json: () => Promise.resolve({ok: true}),
                clone: function () {
                    return this;
                },
            });
        });

        const response = await http.sendJsonPostRequest('/test/', {name: 'Ada'});

        expect(response.data).toEqual({ok: true});
        expect(capturedOptions.method).toBe('POST');
        expect(capturedOptions.headers['Content-Type']).toBe('application/json');
        expect(capturedOptions.headers['X-CSRFToken']).toBe('test-csrf-token');
        expect(capturedOptions.body).toBe(JSON.stringify({name: 'Ada'}));
    });

    it('throws response text for non-ok responses', async () => {
        global.fetch = mock(() => Promise.resolve({
            ok: false,
            status: 500,
            text: () => Promise.resolve('Nope'),
        }));

        try {
            await http.sendRequest('/broken/', {method: 'GET', contentType: 'application/json'});
            throw new Error('Expected request to fail');
        } catch (error) {
            expect(error).toBeInstanceOf(GlueHttpError);
            expect(error.message).toBe('An error occurred when sending a glue http request: Nope');
            expect(error.status).toBe(500);
            expect(error.code).toBeNull();
            expect(error.isGlueError).toBe(false);
            expect(error.responseBody).toBe('Nope');
        }
    });

    it('preserves structured glue error data for non-ok responses', async () => {
        global.fetch = mock(() => Promise.resolve({
            ok: false,
            status: 403,
            text: () => Promise.resolve(JSON.stringify({
                error: {
                    code: 'proxy_policy_expired',
                    message: "Policy for proxy 'thing' has expired.",
                    status: 403,
                    details: {proxy: 'thing'},
                },
            })),
        }));

        try {
            await http.sendRequest('/broken/', {method: 'GET', contentType: 'application/json'});
            throw new Error('Expected request to fail');
        } catch (error) {
            expect(error).toBeInstanceOf(GlueHttpError);
            expect(error.message).toBe(
                "An error occurred when sending a glue http request: Policy for proxy 'thing' has expired."
            );
            expect(error.code).toBe('proxy_policy_expired');
            expect(error.status).toBe(403);
            expect(error.isGlueError).toBe(true);
            expect(error.details).toEqual({proxy: 'thing'});
            expect(error.payload.message).toBe("Policy for proxy 'thing' has expired.");
        }
    });

    it('omits content-type for FormData requests', async () => {
        let capturedOptions;
        global.fetch = mock((url, options) => {
            capturedOptions = options;
            return Promise.resolve({
                ok: true,
                text: () => Promise.resolve('{}'),
                json: () => Promise.resolve({}),
                clone: function () {
                    return this;
                },
            });
        });

        await http.sendFormPostRequest('/upload/', new FormData());

        expect(capturedOptions.headers['Content-Type']).toBeUndefined();
        expect(capturedOptions.body).toBeInstanceOf(FormData);
    });

    it('sends bound attribute events as FormData', async () => {
        let capturedUrl;
        let capturedBody;
        const policy = createFormPolicy();

        global.fetch = mock((url, options) => {
            capturedUrl = url;
            capturedBody = options.body;
            return Promise.resolve({
                ok: true,
                text: () => Promise.resolve('{}'),
                json: () => Promise.resolve({}),
                clone: function () {
                    return this;
                },
            });
        });

        await http.sendAttributeEventRequest({
            name: 'contact',
            attribute: 'GlueFormProxy.validate',
            eventKwargs: {step: 2},
            policy,
            state: {instance_data: {name: 'Ada'}},
        });

        expect(capturedUrl).toBe('/__dg__/bound_attribute_event/contact/GlueFormProxy.validate/');
        expect(JSON.parse(capturedBody.get('policy'))).toEqual(policy);
        expect(JSON.parse(capturedBody.get('state'))).toEqual({instance_data: {name: 'Ada'}});
        expect(JSON.parse(capturedBody.get('event_kwargs'))).toEqual({step: 2});
    });

    it('extracts nested file values into separate FormData fields', async () => {
        let capturedBody;
        const file = new File(['content'], 'avatar.txt');

        global.fetch = mock((url, options) => {
            capturedBody = options.body;
            return Promise.resolve({
                ok: true,
                text: () => Promise.resolve('{}'),
                json: () => Promise.resolve({}),
                clone: function () {
                    return this;
                },
            });
        });

        await http.sendAttributeEventRequest({
            name: 'contact',
            attribute: 'GlueFormProxy.save',
            policy: createFormPolicy(),
            state: {instance_data: {name: 'Ada', avatar: file}},
        });

        expect(capturedBody.get('avatar')).toBe(file);
        expect(JSON.parse(capturedBody.get('state'))).toEqual({instance_data: {name: 'Ada'}});
    });

    it('extracts arrays of files while preserving non-file array values', async () => {
        const fileA = new File(['a'], 'a.txt');
        const fileB = new File(['b'], 'b.txt');

        const {files, data} = http._extractFiles({
            attachments: [fileA, fileB, 'keep'],
            tags: ['alpha', 'beta'],
        });

        expect(files.attachments).toEqual([fileA, fileB]);
        expect(data.attachments).toEqual(['keep']);
        expect(data.tags).toEqual(['alpha', 'beta']);
    });

    it('extracts FileList values without including them in JSON state', async () => {
        const input = document.createElement('input');
        input.type = 'file';

        const {files, data} = http._extractFiles({uploads: input.files});

        expect(files.uploads).toBe(input.files);
        expect(data.uploads).toBeUndefined();
    });
});
