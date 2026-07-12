import {describe, expect, it} from 'bun:test';
import {
    createFormPolicy,
    createMockFetch,
    createMockHttp,
    createState,
    setupCookieMock,
} from './testUtils';

describe('testUtils', () => {
    it('creates mock fetch responses by URL', async () => {
        const fetch = createMockFetch({
            '/ok': {data: {success: true}},
        });

        const response = await fetch('/ok');

        expect(response.ok).toBe(true);
        expect(await response.json()).toEqual({success: true});
    });

    it('sets document.cookie for csrf tests', () => {
        setupCookieMock({csrftoken: 'abc 123'});
        expect(document.cookie).toBe('csrftoken=abc%20123');
    });

    it('creates current policy fixtures', () => {
        const policy = createFormPolicy();
        expect(policy.subject_details.namespace).toBe('form');
        expect(policy.bound_attributes['GlueFormProxy.validate']).toEqual({});
    });

    it('creates current state fixtures', () => {
        expect(createState({name: 'Ada'}).instance_data.name).toBe('Ada');
    });

    it('creates mock http event responses', async () => {
        const http = createMockHttp({result: {ok: true}, state: {}});
        const response = await http.sendAttributeEventRequest({});
        expect(response.data.result.ok).toBe(true);
    });
});
