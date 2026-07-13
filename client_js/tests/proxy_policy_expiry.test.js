import {afterEach, describe, expect, it, mock} from 'bun:test';
import GlueConfig from '../src/config';
import GlueHttp from '../src/http';
import GlueQuerySetProxy from '../src/proxies/queryset';
import {createQuerySetPolicy, setupCookieMock} from './testUtils';

describe('proxy policy expiry request path', () => {
    afterEach(() => {
        global.fetch = undefined;
    });

    it('surfaces expired policy rejections from bound attribute requests', async () => {
        setupCookieMock({csrftoken: 'csrf-token'});

        const expiredPolicy = {
            ...createQuerySetPolicy(),
            name: 'gorillas',
            access: 'view',
            created_at: 1,
            original_signature: 'server-generated-signature',
        };

        let submittedPolicy;
        global.fetch = mock(async (_url, options) => {
            submittedPolicy = JSON.parse(options.body.get('policy'));

            return {
                ok: false,
                text: () => Promise.resolve("Policy for proxy 'gorillas' has expired."),
                clone: function () {
                    return this;
                },
            };
        });

        const http = new GlueHttp(new GlueConfig({
            attributeEventUrlPath: '/__dg__/bound_attribute_event/',
            glueViewUrlPath: '/__dg__/glue_view/',
        }));

        const proxy = new GlueQuerySetProxy({
            http,
            name: 'gorillas',
            policy: expiredPolicy,
            state: {list_data: []},
        });

        await expect(proxy.all()).rejects.toThrow("Policy for proxy 'gorillas' has expired.");
        expect(submittedPolicy.created_at).toBe(1);
        expect(global.fetch.mock.calls[0][0]).toBe('/__dg__/bound_attribute_event/gorillas/GlueQuerySetProxy.query_with_params/');
        expect(global.fetch.mock.calls[0][1].headers['X-CSRFToken']).toBe('csrf-token');
    });
});
