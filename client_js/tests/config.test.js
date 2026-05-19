import { describe, it, expect } from 'bun:test';
import GlueConfig from '../src/config';

describe('GlueConfig', () => {
    describe('constructor defaults', () => {
        it('sets default requestTimeoutSeconds', () => {
            const config = new GlueConfig({
                actionUrlPath: '/__dg__/action/',
                keepLiveUrlPath: '/__dg__/keep_live/',
                glueViewUrlPath: '/__dg__/glue_view/',
            });
            expect(config.requestTimeoutSeconds).toBe(30);
        });

        it('sets default sessionExpiryMessage', () => {
            const config = new GlueConfig({
                actionUrlPath: '/__dg__/action/',
                keepLiveUrlPath: '/__dg__/keep_live/',
                glueViewUrlPath: '/__dg__/glue_view/',
            });
            expect(config.sessionExpiryMessage).toBe('Session expired. Do you want to reload the page?');
        });

        it('sets default keepLiveIntervalSeconds', () => {
            const config = new GlueConfig({
                actionUrlPath: '/__dg__/action/',
                keepLiveUrlPath: '/__dg__/keep_live/',
                glueViewUrlPath: '/__dg__/glue_view/',
            });
            expect(config.keepLiveIntervalSeconds).toBe(600);
        });

        it('sets minimumKeepLiveIntervalSeconds', () => {
            const config = new GlueConfig({
                actionUrlPath: '/__dg__/action/',
                keepLiveUrlPath: '/__dg__/keep_live/',
                glueViewUrlPath: '/__dg__/glue_view/',
            });
            expect(config.minimumKeepLiveIntervalSeconds).toBe(120);
        });
    });

    describe('custom values', () => {
        it('accepts custom requestTimeoutSeconds', () => {
            const config = new GlueConfig({
                requestTimeoutSeconds: 60,
                actionUrlPath: '/__dg__/action/',
                keepLiveUrlPath: '/__dg__/keep_live/',
                glueViewUrlPath: '/__dg__/glue_view/',
            });
            expect(config.requestTimeoutSeconds).toBe(60);
        });

        it('accepts custom sessionExpiryMessage', () => {
            const config = new GlueConfig({
                sessionExpiryMessage: 'Custom message',
                actionUrlPath: '/__dg__/action/',
                keepLiveUrlPath: '/__dg__/keep_live/',
                glueViewUrlPath: '/__dg__/glue_view/',
            });
            expect(config.sessionExpiryMessage).toBe('Custom message');
        });

        it('accepts custom keepLiveIntervalSeconds', () => {
            const config = new GlueConfig({
                keepLiveIntervalSeconds: 300,
                actionUrlPath: '/__dg__/action/',
                keepLiveUrlPath: '/__dg__/keep_live/',
                glueViewUrlPath: '/__dg__/glue_view/',
            });
            expect(config.keepLiveIntervalSeconds).toBe(300);
        });

        it('stores url paths', () => {
            const config = new GlueConfig({
                actionUrlPath: '/custom/action/',
                keepLiveUrlPath: '/custom/keep_live/',
                glueViewUrlPath: '/custom/glue_view/',
            });
            expect(config.actionUrlPath).toBe('/custom/action/');
            expect(config.keepLiveUrlPath).toBe('/custom/keep_live/');
            expect(config.glueViewUrlPath).toBe('/custom/glue_view/');
        });
    });
});
