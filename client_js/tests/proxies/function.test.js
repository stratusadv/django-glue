import {describe, it, expect, beforeEach, mock} from 'bun:test';
import GlueFunctionProxy from '../../src/proxies/function';

describe('GlueFunctionProxy', () => {
    let mockHttp;
    let fn;

    const contextData = {
        subject_type: 'Function',
        function_path: 'myapp.utils.add_numbers',
        params: [
            {name: 'a', type: 'int'},
            {name: 'b', type: 'int'},
        ],
        actions: {
            execute: {action_data: 'ActionPayloadSchema'},
        },
    };

    beforeEach(() => {
        mockHttp = {
            sendActionRequest: mock(async (req) => {
                return {
                    data: {
                        result: req.payload.a + req.payload.b,
                    },
                };
            }),
        };

        fn = GlueFunctionProxy.create({
            http: mockHttp,
            proxyUniqueName: 'add',
            contextData: contextData,
        });
    });

    describe('static name', () => {
        it('is function for namespace mapping', () => {
            expect(GlueFunctionProxy.name).toBe('function');
        });
    });

    describe('static create', () => {
        it('returns a callable function', () => {
            expect(typeof fn).toBe('function');
        });

        it('attaches metadata properties', () => {
            expect(fn._uniqueName).toBe('add');
            expect(fn._contextData).toBe(contextData);
            expect(fn._params).toEqual([
                {name: 'a', type: 'int'},
                {name: 'b', type: 'int'},
            ]);
        });

        it('attaches listener methods', () => {
            expect(typeof fn.addListener).toBe('function');
            expect(typeof fn.removeListener).toBe('function');
            expect(typeof fn.clearListeners).toBe('function');
        });
    });

    describe('callable invocation', () => {
        it('maps positional args to named params and calls execute', async () => {
            const result = await fn(3, 4);
            expect(result).toBe(7);
        });

        it('sends correct action request', async () => {
            await fn(10, 20);

            expect(mockHttp.sendActionRequest).toHaveBeenCalledWith(
                expect.objectContaining({
                    uniqueName: 'add',
                    action: 'execute',
                    payload: {a: 10, b: 20},
                })
            );
        });

        it('handles fewer args than params', async () => {
            mockHttp.sendActionRequest = mock(async (req) => {
                return {
                    data: {
                        result: (req.payload.a || 0) + (req.payload.b || 0),
                    },
                };
            });

            const result = await fn(5);
            expect(result).toBe(5);
        });

        it('handles extra args beyond params', async () => {
            mockHttp.sendActionRequest = mock(async (req) => {
                return {
                    data: {
                        result: req.payload.a + req.payload.b,
                    },
                };
            });

            const result = await fn(1, 2, 999);
            expect(result).toBe(3);
        });

        it('handles various argument types', async () => {
            mockHttp.sendActionRequest = mock(async (req) => {
                return {
                    data: {
                        result: `${req.payload.greeting}, ${req.payload.name}!`,
                    },
                };
            });

            const greetFn = GlueFunctionProxy.create({
                http: mockHttp,
                proxyUniqueName: 'greet',
                contextData: {
                    subject_type: 'Function',
                    function_path: 'myapp.utils.greet',
                    params: [
                        {name: 'greeting', type: 'str'},
                        {name: 'name', type: 'str'},
                    ],
                    actions: {execute: {}},
                },
            });

            const result = await greetFn('Hello', 'World');
            expect(result).toBe('Hello, World!');
        });
    });

    describe('listener events', () => {
        it('fires before listeners before execute', async () => {
            const events = [];

            mockHttp.sendActionRequest = mock(async () => {
                events.push('request');
                return {data: {result: 42}};
            });

            fn.addListener('execute', () => {
                events.push('before');
            }, 'before');

            await fn(1, 2);

            expect(events).toEqual(['before', 'request']);
        });

        it('fires after listeners with result', async () => {
            let capturedEvent = null;

            fn.addListener('execute', (event) => {
                capturedEvent = event;
            }, 'after');

            await fn(3, 4);

            expect(capturedEvent.result).toEqual({result: 7});
            expect(capturedEvent.action).toBe('execute');
        });

        it('fires error listeners on failure', async () => {
            let capturedError = null;

            mockHttp.sendActionRequest = mock(async () => {
                throw new Error('server error');
            });

            fn.addListener('execute', (event) => {
                capturedError = event.error;
            }, 'error');

            await expect(fn(1, 2)).rejects.toThrow('server error');
            expect(capturedError).toBeInstanceOf(Error);
        });
    });

    describe('removeListener and clearListeners', () => {
        it('removes a specific listener', async () => {
            let callCount = 0;
            const callback = () => { callCount++; };

            fn.addListener('execute', callback, 'after');
            fn.removeListener('execute', callback, 'after');

            await fn(1, 2);
            expect(callCount).toBe(0);
        });

        it('clears all listeners', async () => {
            let callCount = 0;
            fn.addListener('execute', () => { callCount++; }, 'after');
            fn.clearListeners();

            await fn(1, 2);
            expect(callCount).toBe(0);
        });
    });
});
