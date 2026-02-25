import { describe, it, expect, beforeEach } from 'bun:test';
import { getConfig, setConfig, resetConfig } from '../src/config';

describe('config', () => {
    beforeEach(() => {
        resetConfig();
    });

    describe('getConfig', () => {
        it('returns default config', () => {
            const config = getConfig();
            expect(config.requestTimeoutMs).toBe(30000);
        });
    });

    describe('setConfig', () => {
        it('merges new config with existing', () => {
            setConfig({ requestTimeoutMs: 5000 });
            const config = getConfig();
            expect(config.requestTimeoutMs).toBe(5000);
        });

        it('preserves existing values not overwritten', () => {
            setConfig({ customOption: 'test' });
            const config = getConfig();
            expect(config.requestTimeoutMs).toBe(30000);
            expect(config.customOption).toBe('test');
        });
    });

    describe('resetConfig', () => {
        it('restores default config', () => {
            setConfig({ requestTimeoutMs: 1000 });
            resetConfig();
            const config = getConfig();
            expect(config.requestTimeoutMs).toBe(30000);
        });
    });
});
