import { describe, it, expect, beforeEach, afterEach, mock } from 'bun:test';
import { createMockFetch, setupCookieMock, createMockcontract } from './testUtils';

describe('testUtils', () => {
    describe('createMockFetch', () => {
        it('returns configured response for matching URL', async () => {
            const mockFn = createMockFetch({
                '/api/test': { ok: true, data: { result: 'ok' } }
            });

            const res = await mockFn('/api/test');
            expect(res.ok).toBe(true);
            expect(await res.json()).toEqual({ result: 'ok' });
        });

        it('returns default response for unknown URL', async () => {
            const mockFn = createMockFetch({});

            const res = await mockFn('/unknown');
            expect(res.ok).toBe(true);
            expect(await res.json()).toEqual({});
        });

        it('supports error responses', async () => {
            const mockFn = createMockFetch({
                '/api/error': { ok: false, data: { error: 'bad' } }
            });

            const res = await mockFn('/api/error');
            expect(res.ok).toBe(false);
        });

        it('returns text via text()', async () => {
            const mockFn = createMockFetch({
                '/api/test': { data: { key: 'value' } }
            });

            const res = await mockFn('/api/test');
            expect(await res.text()).toBe('{"key":"value"}');
        });

        it('supports clone()', async () => {
            const mockFn = createMockFetch({
                '/api/test': { data: {} }
            });

            const res = await mockFn('/api/test');
            expect(res.clone()).toBe(res);
        });
    });

    describe('setupCookieMock', () => {
        it('sets cookie string from object', () => {
            setupCookieMock({ foo: 'bar', baz: 'qux' });
            expect(document.cookie).toContain('foo=bar');
            expect(document.cookie).toContain('baz=qux');
        });

        it('encodes cookie values', () => {
            setupCookieMock({ token: 'a b' });
            expect(document.cookie).toContain('token=a%20b');
        });

        it('handles empty cookies object', () => {
            setupCookieMock({});
            expect(document.cookie).toBe('');
        });
    });

    describe('createMockcontract', () => {
        it('returns object with fields, actions, initial', () => {
            const data = createMockcontract(
                { name: {} },
                { get: {} },
                { name: 'init' }
            );

            expect(data.fields).toEqual({ name: {} });
            expect(data.actions).toEqual({ get: {} });
            expect(data.initial).toEqual({ name: 'init' });
        });

        it('returns empty defaults', () => {
            const data = createMockcontract();
            expect(data.fields).toEqual({});
            expect(data.actions).toEqual({});
            expect(data.initial).toEqual({});
        });
    });
});
