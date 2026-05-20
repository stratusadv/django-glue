import { describe, it, expect, beforeEach, afterEach, mock } from 'bun:test';
import GlueHttp from '../src/http';
import { setupCookieMock } from './testUtils';

describe('GlueHttp', () => {
    let http;
    let originalFetch;

    const createConfig = () => ({
        requestTimeoutSeconds: 30,
        actionUrlPath: '/__dg__/action/',
        keepLiveUrlPath: '/__dg__/keep_live/',
        glueViewUrlPath: '/__dg__/glue_view/',
    });

    beforeEach(() => {
        originalFetch = global.fetch;
        setupCookieMock({ csrftoken: 'test-csrf-token' });
        http = new GlueHttp(createConfig());
    });

    afterEach(() => {
        global.fetch = originalFetch;
    });

    describe('getCookie', () => {
        it('returns cookie value by name', () => {
            expect(http.getCookie('csrftoken')).toBe('test-csrf-token');
        });

        it('returns null for missing cookie', () => {
            expect(http.getCookie('nonexistent')).toBeNull();
        });
    });

    describe('sendRequest', () => {
        it('sends GET request with correct headers', async () => {
            let capturedOptions = null;
            global.fetch = mock((url, options) => {
                capturedOptions = options;
                return Promise.resolve({
                    ok: true,
                    text: () => Promise.resolve('{}'),
                    json: () => Promise.resolve({}),
                    clone: function() { return this; }
                });
            });

            await http.sendRequest('/test', { method: 'GET', contentType: 'application/json' });

            expect(capturedOptions.method).toBe('GET');
            expect(capturedOptions.headers['Content-Type']).toBe('application/json');
            expect(capturedOptions.signal).toBeInstanceOf(AbortSignal);
        });

        it('includes CSRF token for protected requests', async () => {
            // Mock getCookie to return a token
            const testHttp = new GlueHttp(createConfig());
            testHttp.getCookie = (name) => name === 'csrftoken' ? 'test-csrf-token' : null;

            let capturedOptions = null;
            global.fetch = mock((url, options) => {
                capturedOptions = options;
                return Promise.resolve({
                    ok: true,
                    text: () => Promise.resolve('{}'),
                    json: () => Promise.resolve({}),
                    clone: function() { return this; }
                });
            });

            // Must pass csrfProtected: true explicitly (source bug: default only applies when no args)
            await testHttp.sendRequest('/test', {
                method: 'POST',
                contentType: 'application/json',
                body: '{}',
                csrfProtected: true
            });

            expect(capturedOptions.headers['X-CSRFToken']).toBe('test-csrf-token');
        });

        it('sends POST request with body', async () => {
            let capturedOptions = null;
            global.fetch = mock((url, options) => {
                capturedOptions = options;
                return Promise.resolve({
                    ok: true,
                    text: () => Promise.resolve('{}'),
                    json: () => Promise.resolve({}),
                    clone: function() { return this; }
                });
            });

            const body = JSON.stringify({ key: 'value' });
            await http.sendRequest('/test', { method: 'POST', body });

            expect(capturedOptions.method).toBe('POST');
            expect(capturedOptions.body).toBe(body);
        });

        it('skips CSRF token when csrfProtected is false', async () => {
            let capturedOptions = null;
            global.fetch = mock((url, options) => {
                capturedOptions = options;
                return Promise.resolve({
                    ok: true,
                    text: () => Promise.resolve('{}'),
                    json: () => Promise.resolve({}),
                    clone: function() { return this; }
                });
            });

            await http.sendRequest('/test', { method: 'GET', csrfProtected: false });

            expect(capturedOptions.headers['X-CSRFToken']).toBeUndefined();
        });

        it('removes Content-Type for multipart/form-data', async () => {
            let capturedOptions = null;
            global.fetch = mock((url, options) => {
                capturedOptions = options;
                return Promise.resolve({
                    ok: true,
                    text: () => Promise.resolve('{}'),
                    json: () => Promise.resolve({}),
                    clone: function() { return this; }
                });
            });

            await http.sendRequest('/test', {
                method: 'POST',
                body: new FormData(),
                contentType: 'multipart/form-data',
            });

            expect(capturedOptions.headers['Content-Type']).toBeUndefined();
        });

        it('throws error on non-ok response', async () => {
            global.fetch = mock(() => Promise.resolve({
                ok: false,
                text: () => Promise.resolve('Server error'),
                clone: function() { return this; }
            }));

            await expect(http.sendRequest('/test', { method: 'GET' }))
                .rejects.toThrow('An error occurred when sending a glue http request');
        });

        it('returns response object with ok, body, httpResponse, data', async () => {
            const mockResponse = {
                ok: true,
                text: () => Promise.resolve('{"result": "ok"}'),
                json: () => Promise.resolve({ result: 'ok' }),
                clone: function() { return this; }
            };
            global.fetch = mock(() => Promise.resolve(mockResponse));

            const result = await http.sendRequest('/test', { method: 'GET' });

            expect(result.ok).toBe(true);
            expect(result.body).toBe('{"result": "ok"}');
            expect(result.httpResponse).toBe(mockResponse);
            expect(result.data).toEqual({ result: 'ok' });
        });
    });

    describe('sendJsonPostRequest', () => {
        it('sends POST with JSON body', async () => {
            let capturedOptions = null;
            global.fetch = mock((url, options) => {
                capturedOptions = options;
                return Promise.resolve({
                    ok: true,
                    text: () => Promise.resolve('{}'),
                    json: () => Promise.resolve({}),
                    clone: function() { return this; }
                });
            });

            await http.sendJsonPostRequest('/test', { key: 'value' });

            expect(capturedOptions.method).toBe('POST');
            expect(capturedOptions.body).toBe(JSON.stringify({ key: 'value' }));
            expect(capturedOptions.headers['Content-Type']).toBe('application/json');
        });

        it('sends empty object when data is null', async () => {
            let capturedOptions = null;
            global.fetch = mock((url, options) => {
                capturedOptions = options;
                return Promise.resolve({
                    ok: true,
                    text: () => Promise.resolve('{}'),
                    json: () => Promise.resolve({}),
                    clone: function() { return this; }
                });
            });

            await http.sendJsonPostRequest('/test', null);

            expect(capturedOptions.body).toBe(JSON.stringify({}));
        });
    });

    describe('sendActionRequest', () => {
        it('sends JSON action request with correct URL and payload', async () => {
            let capturedUrl = null;
            let capturedOptions = null;
            global.fetch = mock((url, options) => {
                capturedUrl = url;
                capturedOptions = options;
                return Promise.resolve({
                    ok: true,
                    text: () => Promise.resolve('{"success": true}'),
                    json: () => Promise.resolve({ success: true }),
                    clone: function() { return this; }
                });
            });

            await http.sendActionRequest({
                uniqueName: 'task',
                action: 'save',
                payload: { title: 'Test' },
                contextData: { subject_type: 'Model' }
            });

            expect(capturedUrl).toBe('/__dg__/action/task/save/');
            expect(capturedOptions.body).toBe(JSON.stringify({
                post_data: { title: 'Test' },
                context_data: { subject_type: 'Model' }
            }));
        });

        it('sends FormData action request for file uploads', async () => {
            let capturedUrl = null;
            let capturedOptions = null;
            global.fetch = mock((url, options) => {
                capturedUrl = url;
                capturedOptions = options;
                return Promise.resolve({
                    ok: true,
                    text: () => Promise.resolve('{"success": true}'),
                    json: () => Promise.resolve({ success: true }),
                    clone: function() { return this; }
                });
            });

            const formData = new FormData();
            formData.append('file', new Blob(['content']), 'test.txt');

            await http.sendActionRequest({
                uniqueName: 'task',
                action: 'save',
                payload: formData,
                contextData: { subject_type: 'Model' }
            });

            expect(capturedUrl).toBe('/__dg__/action/task/save/');
            expect(capturedOptions.body).toBeInstanceOf(FormData);
            expect(capturedOptions.body.get('context_data')).toBe(JSON.stringify({ subject_type: 'Model' }));
        });
    });

    describe('sendKeepLiveRequest', () => {
        it('posts to keep_live URL with unique_names', async () => {
            let capturedUrl = null;
            let capturedOptions = null;
            global.fetch = mock((url, options) => {
                capturedUrl = url;
                capturedOptions = options;
                return Promise.resolve({
                    ok: true,
                    text: () => Promise.resolve('{}'),
                    json: () => Promise.resolve({}),
                    clone: function() { return this; }
                });
            });

            await http.sendKeepLiveRequest(['proxy1', 'proxy2']);

            expect(capturedUrl).toBe('/__dg__/keep_live/');
            expect(capturedOptions.body).toBe(JSON.stringify({ unique_names: ['proxy1', 'proxy2'] }));
        });
    });
});
