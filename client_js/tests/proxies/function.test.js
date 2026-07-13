import {afterEach, describe, expect, it, mock} from 'bun:test';
import GlueFunctionProxy from '../../src/proxies/function';
import {createFunctionPolicy, createMockHttp} from '../testUtils';

describe('GlueFunctionProxy', () => {
    afterEach(() => {
        delete globalThis.Glue;
    });

    it('creates a callable wrapper that maps declared params into event kwargs', async () => {
        const http = createMockHttp({
            result: {result: 12},
            state: null,
        });
        const fn = GlueFunctionProxy.create({
            http,
            name: 'calculate',
            policy: createFunctionPolicy(),
        });

        const result = await fn({amount: 10, tax: 2, ignored: true});

        expect(result).toBe(12);
        expect(http.sendAttributeEventRequest).toHaveBeenCalledWith({
            name: 'calculate',
            attribute: 'GlueFunctionProxy.execute',
            eventKwargs: {amount: 10, tax: 2},
            policy: fn._policy,
            state: null,
        });
    });

    it('rejects non-object arguments', async () => {
        const fn = GlueFunctionProxy.create({
            http: createMockHttp(),
            name: 'calculate',
            policy: createFunctionPolicy(),
        });

        await expect(fn(['not', 'object'])).rejects.toThrow(
            'Must pass glue function arguments as fields in an object.',
        );
    });

    it('exposes listener methods on the callable wrapper', async () => {
        const http = createMockHttp({result: {result: 5}, state: null});
        const fn = GlueFunctionProxy.create({
            http,
            name: 'calculate',
            policy: createFunctionPolicy(),
        });
        const after = mock(() => {});

        fn.addListener('execute', after);
        await fn({amount: 5});

        expect(after.mock.calls[0][0].result).toEqual({result: 5});
    });

    it('exposes proxy-specific message handling on the callable wrapper', async () => {
        const http = createMockHttp({
            result: {result: 5},
            state: null,
            messages: [{level: 25, level_tag: 'success', message: 'Calculated', tags: 'success'}],
        });
        const fn = GlueFunctionProxy.create({
            http,
            name: 'calculate',
            policy: createFunctionPolicy(),
        });
        globalThis.Glue = {_onMessage: mock(() => {})};
        const onMessage = mock(() => {});

        fn.onMessage(onMessage);
        await fn({amount: 5});

        expect(onMessage).toHaveBeenCalledTimes(1);
        expect(onMessage.mock.calls[0][0].messages[0].message).toBe('Calculated');
        expect(onMessage.mock.calls[0][0].attribute).toBe('GlueFunctionProxy.execute');
    });

    it('uses the execute method defined by _defineAttributeProperties', async () => {
        const http = createMockHttp({result: {result: 42}, state: null});
        const policy = createFunctionPolicy();
        const fn = GlueFunctionProxy.create({http, name: 'test_fn', policy});

        // The internal instance should have execute defined as a method
        // This test ensures we're using the bound attribute system, not a hardcoded path
        expect(policy.bound_attributes['GlueFunctionProxy.execute']).toBeDefined();

        await fn({amount: 1});

        // Verify the full attribute path is sent to the server
        const call = http.sendAttributeEventRequest.mock.calls[0][0];
        expect(call.attribute).toBe('GlueFunctionProxy.execute');
        expect(call.attribute).not.toBe('execute');
    });

    it('unwraps nested result from server response', async () => {
        // Server returns {result: {result: actualValue}, state: ...}
        // The function proxy should unwrap to return actualValue
        const http = createMockHttp({
            result: {result: {data: 'nested', count: 5}},
            state: null,
        });
        const fn = GlueFunctionProxy.create({
            http,
            name: 'getData',
            policy: createFunctionPolicy(),
        });

        const result = await fn({});

        expect(result).toEqual({data: 'nested', count: 5});
    });
});
