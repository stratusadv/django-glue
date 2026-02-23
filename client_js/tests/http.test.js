import { sendHttpRequest, sendJsonPostRequest, sendActionRequest, sendKeepLiveRequest } from '../src/http';
import { resetConfig, setConfig } from '../src/config';
import { createMockFetch, setupCookieMock } from './testUtils';

// Mock the constants module
jest.mock('../src/constants', () => ({
    actionUrl: '/django_glue/',
    keepLiveUrl: '/django_glue/keep_live/'
}));

describe('http', () => {
    let originalFetch;

    beforeEach(() => {
        originalFetch = global.fetch;
        resetConfig();
        setupCookieMock({ csrftoken: 'test-csrf-token' });
    });

    afterEach(() => {
        global.fetch = originalFetch;
        jest.clearAllMocks();
    });

    describe('sendHttpRequest', () => {
        it('sends request with correct method', async () => {
            global.fetch = createMockFetch({
                '/test': { ok: true, data: { result: 'success' } }
            });

            const result = await sendHttpRequest('/test', { method: 'GET' });

            expect(result.ok).toBe(true);
            expect(result.data).toEqual({ result: 'success' });
        });

        it('includes CSRF token for protected requests', async () => {
            global.fetch = jest.fn().mockResolvedValue({
                ok: true,
                text: () => Promise.resolve('{}'),
                json: () => Promise.resolve({}),
                clone: function() { return this; }
            });

            await sendHttpRequest('/test', { method: 'POST', csrfProtected: true });

            expect(global.fetch).toHaveBeenCalledWith(
                '/test',
                expect.objectContaining({
                    headers: expect.objectContaining({
                        'X-CSRFToken': 'test-csrf-token'
                    })
                })
            );
        });

        it('throws error on non-ok response', async () => {
            global.fetch = jest.fn().mockResolvedValue({
                ok: false,
                text: () => Promise.resolve('Server error'),
                clone: function() { return this; }
            });

            await expect(sendHttpRequest('/test', {}))
                .rejects.toThrow('An error occurred when sending a glue http request');
        });

        it('includes body for POST requests', async () => {
            global.fetch = jest.fn().mockResolvedValue({
                ok: true,
                text: () => Promise.resolve('{}'),
                json: () => Promise.resolve({}),
                clone: function() { return this; }
            });

            await sendHttpRequest('/test', {
                method: 'POST',
                body: JSON.stringify({ key: 'value' }),
                contentType: 'application/json'
            });

            expect(global.fetch).toHaveBeenCalledWith(
                '/test',
                expect.objectContaining({
                    method: 'POST',
                    body: JSON.stringify({ key: 'value' })
                })
            );
        });

        it('uses AbortController for timeout', async () => {
            // Verify AbortController is used - actual timeout testing is complex with fake timers
            global.fetch = jest.fn().mockResolvedValue({
                ok: true,
                text: () => Promise.resolve('{}'),
                json: () => Promise.resolve({}),
                clone: function() { return this; }
            });

            await sendHttpRequest('/test', { method: 'GET' });

            // Verify fetch was called with a signal (AbortController)
            expect(global.fetch).toHaveBeenCalledWith(
                '/test',
                expect.objectContaining({
                    signal: expect.any(AbortSignal)
                })
            );
        });
    });

    describe('sendJsonPostRequest', () => {
        it('sends POST with JSON body', async () => {
            global.fetch = jest.fn().mockResolvedValue({
                ok: true,
                text: () => Promise.resolve('{}'),
                json: () => Promise.resolve({}),
                clone: function() { return this; }
            });

            await sendJsonPostRequest('/test', { key: 'value' });

            expect(global.fetch).toHaveBeenCalledWith(
                '/test',
                expect.objectContaining({
                    method: 'POST',
                    body: JSON.stringify({ key: 'value' }),
                    headers: expect.objectContaining({
                        'Content-Type': 'application/json'
                    })
                })
            );
        });

        it('sends empty object when data is null', async () => {
            global.fetch = jest.fn().mockResolvedValue({
                ok: true,
                text: () => Promise.resolve('{}'),
                json: () => Promise.resolve({}),
                clone: function() { return this; }
            });

            await sendJsonPostRequest('/test', null);

            expect(global.fetch).toHaveBeenCalledWith(
                '/test',
                expect.objectContaining({
                    body: JSON.stringify({})
                })
            );
        });
    });

    describe('sendActionRequest', () => {
        it('posts to action URL', async () => {
            global.fetch = createMockFetch({
                '/django_glue/': { ok: true, data: { success: true } }
            });

            const result = await sendActionRequest({ unique_name: 'test', action: 'get' });

            expect(result.data).toEqual({ success: true });
        });
    });

    describe('sendKeepLiveRequest', () => {
        it('posts to keep_live URL with unique_names', async () => {
            global.fetch = jest.fn().mockResolvedValue({
                ok: true,
                text: () => Promise.resolve('{}'),
                json: () => Promise.resolve({}),
                clone: function() { return this; }
            });

            await sendKeepLiveRequest(['proxy1', 'proxy2']);

            expect(global.fetch).toHaveBeenCalledWith(
                '/django_glue/keep_live/',
                expect.objectContaining({
                    body: JSON.stringify({ unique_names: ['proxy1', 'proxy2'] })
                })
            );
        });
    });
});