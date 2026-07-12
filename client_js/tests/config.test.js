import {describe, expect, it} from 'bun:test';
import GlueConfig from '../src/config';

describe('GlueConfig', () => {
    it('sets defaults for request timeout, expiry message, and keep live interval', () => {
        const config = new GlueConfig({
            attributeEventUrlPath: '/__dg__/bound_attribute_event/',
            keepLiveUrlPath: '/__dg__/keep_live/',
            glueViewUrlPath: '/__dg__/glue_view/',
        });

        expect(config.requestTimeoutSeconds).toBe(30);
        expect(config.sessionExpiryMessage).toBe('Session expired. Do you want to reload the page?');
        expect(config.keepLiveIntervalSeconds).toBe(600);
        expect(config.minimumKeepLiveIntervalSeconds).toBe(120);
    });

    it('stores configured URL paths', () => {
        const config = new GlueConfig({
            attributeEventUrlPath: '/custom/bound_attribute_event/',
            keepLiveUrlPath: '/custom/keep_live/',
            glueViewUrlPath: '/custom/glue_view/',
        });

        expect(config.attributeEventUrlPath).toBe('/custom/bound_attribute_event/');
        expect(config.keepLiveUrlPath).toBe('/custom/keep_live/');
        expect(config.glueViewUrlPath).toBe('/custom/glue_view/');
    });

    it('accepts custom timing and message options', () => {
        const config = new GlueConfig({
            requestTimeoutSeconds: 60,
            sessionExpiryMessage: 'Expired',
            keepLiveIntervalSeconds: 300,
            attributeEventUrlPath: '/events/',
            keepLiveUrlPath: '/keep-live/',
            glueViewUrlPath: '/view/',
        });

        expect(config.requestTimeoutSeconds).toBe(60);
        expect(config.sessionExpiryMessage).toBe('Expired');
        expect(config.keepLiveIntervalSeconds).toBe(300);
    });
});
