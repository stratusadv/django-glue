import {describe, expect, it} from 'bun:test';
import GlueConfig from '../src/config';

describe('GlueConfig', () => {
    it('sets defaults for request timeout', () => {
        const config = new GlueConfig({
            attributeEventUrlPath: '/__dg__/bound_attribute_event/',
            glueViewUrlPath: '/__dg__/glue_view/',
        });

        expect(config.requestTimeoutSeconds).toBe(30);
    });

    it('stores configured URL paths', () => {
        const config = new GlueConfig({
            attributeEventUrlPath: '/custom/bound_attribute_event/',
            glueViewUrlPath: '/custom/glue_view/',
        });

        expect(config.attributeEventUrlPath).toBe('/custom/bound_attribute_event/');
        expect(config.glueViewUrlPath).toBe('/custom/glue_view/');
    });

    it('accepts custom request timeout', () => {
        const config = new GlueConfig({
            requestTimeoutSeconds: 60,
            attributeEventUrlPath: '/events/',
            glueViewUrlPath: '/view/',
        });

        expect(config.requestTimeoutSeconds).toBe(60);
    });
});
