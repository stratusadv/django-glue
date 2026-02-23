import { GlueFormProxy } from '../../src/proxies/form';
import { createMockFetch, setupCookieMock } from '../testUtils';

jest.mock('../../src/constants', () => ({
    actionUrl: '/django_glue/',
    keepLiveUrl: '/django_glue/keep_live/'
}));

describe('GlueFormProxy', () => {
    let originalFetch;

    beforeEach(() => {
        originalFetch = global.fetch;
        setupCookieMock({ csrftoken: 'test-token' });
    });

    afterEach(() => {
        global.fetch = originalFetch;
    });

    function createFormContextData(fields = {}, initial = {}) {
        return {
            fields: fields,
            initial: initial,
            actions: { get: {}, validate: {}, submit: {} }
        };
    }

    describe('constructor', () => {
        it('creates field accessors', () => {
            const contextData = createFormContextData(
                { name: { type: 'text' }, email: { type: 'email' } },
                { name: 'John', email: 'john@example.com' }
            );

            const proxy = new GlueFormProxy({
                proxyUniqueName: 'contact_form',
                contextData
            });

            expect(proxy.name).toBe('John');
            expect(proxy.email).toBe('john@example.com');
        });

        it('initializes values from contextData.initial', () => {
            const contextData = createFormContextData(
                { title: {} },
                { title: 'Initial Value' }
            );

            const proxy = new GlueFormProxy({
                proxyUniqueName: 'form',
                contextData
            });

            expect(proxy.values).toEqual({ title: 'Initial Value' });
        });

        it('starts with empty errors', () => {
            const contextData = createFormContextData({ name: {} }, {});

            const proxy = new GlueFormProxy({
                proxyUniqueName: 'form',
                contextData
            });

            expect(proxy.errors).toEqual({});
        });

        it('stores field definitions', () => {
            const contextData = createFormContextData(
                { name: { type: 'text', required: true } },
                {}
            );

            const proxy = new GlueFormProxy({
                proxyUniqueName: 'form',
                contextData
            });

            expect(proxy.fields).toEqual({ name: { type: 'text', required: true } });
        });

        it('allows setting field values', () => {
            const contextData = createFormContextData({ name: {} }, { name: 'Original' });

            const proxy = new GlueFormProxy({
                proxyUniqueName: 'form',
                contextData
            });

            proxy.name = 'Updated';

            expect(proxy.name).toBe('Updated');
            expect(proxy.values.name).toBe('Updated');
        });
    });

    describe('validate', () => {
        it('sends validate action with current values', async () => {
            global.fetch = jest.fn().mockResolvedValue({
                ok: true,
                text: () => Promise.resolve('{"is_valid": true, "errors": {}}'),
                json: () => Promise.resolve({ is_valid: true, errors: {} }),
                clone: function() { return this; }
            });

            const contextData = createFormContextData(
                { name: {} },
                { name: 'Test' }
            );

            const proxy = new GlueFormProxy({
                proxyUniqueName: 'form',
                contextData
            });

            const result = await proxy.validate();

            expect(result.is_valid).toBe(true);
            expect(global.fetch).toHaveBeenCalledWith(
                '/django_glue/',
                expect.objectContaining({
                    body: expect.stringContaining('"action":"validate"')
                })
            );
        });

        it('updates errors from validation response', async () => {
            global.fetch = jest.fn().mockResolvedValue({
                ok: true,
                text: () => Promise.resolve('{"is_valid": false, "errors": {"name": ["Required"]}}'),
                json: () => Promise.resolve({ is_valid: false, errors: { name: ['Required'] } }),
                clone: function() { return this; }
            });

            const contextData = createFormContextData({ name: {} }, {});

            const proxy = new GlueFormProxy({
                proxyUniqueName: 'form',
                contextData
            });

            await proxy.validate();

            expect(proxy.errors).toEqual({ name: ['Required'] });
        });

        it('clears errors when validation passes', async () => {
            global.fetch = jest.fn().mockResolvedValue({
                ok: true,
                text: () => Promise.resolve('{"is_valid": true, "errors": {}}'),
                json: () => Promise.resolve({ is_valid: true, errors: {} }),
                clone: function() { return this; }
            });

            const contextData = createFormContextData({ name: {} }, { name: 'Valid' });

            const proxy = new GlueFormProxy({
                proxyUniqueName: 'form',
                contextData
            });

            // Set some errors first
            proxy.errors = { name: ['Some error'] };

            await proxy.validate();

            expect(proxy.errors).toEqual({});
        });
    });

    describe('submit', () => {
        it('sends submit action', async () => {
            global.fetch = jest.fn().mockResolvedValue({
                ok: true,
                text: () => Promise.resolve('{"success": true, "data": {}}'),
                json: () => Promise.resolve({ success: true, data: {} }),
                clone: function() { return this; }
            });

            const contextData = createFormContextData({ name: {} }, { name: 'Submit Me' });

            const proxy = new GlueFormProxy({
                proxyUniqueName: 'form',
                contextData
            });

            const result = await proxy.submit();

            expect(result.success).toBe(true);
            expect(global.fetch).toHaveBeenCalledWith(
                '/django_glue/',
                expect.objectContaining({
                    body: expect.stringContaining('"action":"submit"')
                })
            );
        });

        it('updates errors from submit response', async () => {
            global.fetch = jest.fn().mockResolvedValue({
                ok: true,
                text: () => Promise.resolve('{"success": false, "errors": {"email": ["Invalid email"]}}'),
                json: () => Promise.resolve({ success: false, errors: { email: ['Invalid email'] } }),
                clone: function() { return this; }
            });

            const contextData = createFormContextData({ email: {} }, { email: 'bad' });

            const proxy = new GlueFormProxy({
                proxyUniqueName: 'form',
                contextData
            });

            await proxy.submit();

            expect(proxy.errors).toEqual({ email: ['Invalid email'] });
        });

        it('clears errors on successful submit', async () => {
            global.fetch = jest.fn().mockResolvedValue({
                ok: true,
                text: () => Promise.resolve('{"success": true}'),
                json: () => Promise.resolve({ success: true }),
                clone: function() { return this; }
            });

            const contextData = createFormContextData({ name: {} }, { name: 'Valid' });

            const proxy = new GlueFormProxy({
                proxyUniqueName: 'form',
                contextData
            });

            proxy.errors = { name: ['Old error'] };

            await proxy.submit();

            expect(proxy.errors).toEqual({});
        });
    });

    describe('getFieldError', () => {
        it('returns errors for field', () => {
            const contextData = createFormContextData({ name: {} }, {});
            const proxy = new GlueFormProxy({ proxyUniqueName: 'form', contextData });

            proxy.errors = { name: ['Error 1', 'Error 2'] };

            expect(proxy.getFieldError('name')).toEqual(['Error 1', 'Error 2']);
        });

        it('returns empty array for field without errors', () => {
            const contextData = createFormContextData({ name: {} }, {});
            const proxy = new GlueFormProxy({ proxyUniqueName: 'form', contextData });

            expect(proxy.getFieldError('name')).toEqual([]);
            expect(proxy.getFieldError('nonexistent')).toEqual([]);
        });
    });

    describe('hasErrors', () => {
        it('returns false when no errors', () => {
            const contextData = createFormContextData({ name: {} }, {});
            const proxy = new GlueFormProxy({ proxyUniqueName: 'form', contextData });

            expect(proxy.hasErrors()).toBe(false);
        });

        it('returns true when errors exist', () => {
            const contextData = createFormContextData({ name: {} }, {});
            const proxy = new GlueFormProxy({ proxyUniqueName: 'form', contextData });

            proxy.errors = { name: ['Error'] };

            expect(proxy.hasErrors()).toBe(true);
        });
    });

    describe('clearErrors', () => {
        it('removes all errors', () => {
            const contextData = createFormContextData({ name: {}, email: {} }, {});
            const proxy = new GlueFormProxy({ proxyUniqueName: 'form', contextData });

            proxy.errors = { name: ['Error'], email: ['Another error'] };
            proxy.clearErrors();

            expect(proxy.errors).toEqual({});
        });
    });

    describe('getFieldDefinition', () => {
        it('returns field definition', () => {
            const contextData = createFormContextData(
                { name: { type: 'text', required: true } },
                {}
            );

            const proxy = new GlueFormProxy({ proxyUniqueName: 'form', contextData });

            expect(proxy.getFieldDefinition('name')).toEqual({ type: 'text', required: true });
        });

        it('returns null for nonexistent field', () => {
            const contextData = createFormContextData({ name: {} }, {});

            const proxy = new GlueFormProxy({ proxyUniqueName: 'form', contextData });

            expect(proxy.getFieldDefinition('nonexistent')).toBeNull();
        });
    });
});