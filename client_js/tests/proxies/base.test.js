import {afterEach, describe, expect, it, mock} from 'bun:test';
import BaseGlueProxy from '../../src/proxies/base';
import {createMockHttp, createPolicy} from '../testUtils';

describe('BaseGlueProxy', () => {
    afterEach(() => {
        delete globalThis.Glue;
    });

    function makeProxy(response = {result: {ok: true}, state: {loaded: true}}) {
        return new BaseGlueProxy({
            http: createMockHttp(response),
            name: 'thing',
            policy: createPolicy('base', {
                bound_attributes: {
                    'GlueBaseProxy.load': {},
                    'GlueBaseProxy.nested.run': {},
                },
            }),
            state: {loaded: false},
        });
    }

    it('stores constructor arguments and initializes listeners', () => {
        const proxy = makeProxy();

        expect(proxy._name).toBe('thing');
        expect(proxy._state).toEqual({loaded: false});
        expect(proxy._listeners).toEqual({before: {}, after: {}, error: {}});
    });

    it('defines callable functions from bound attribute paths', async () => {
        const proxy = makeProxy();

        expect(typeof proxy.load).toBe('function');
        expect(typeof proxy.nested.run).toBe('function');

        await proxy.nested.run({value: 1});

        expect(proxy.http.sendAttributeEventRequest).toHaveBeenCalledWith({
            name: 'thing',
            attribute: 'GlueBaseProxy.nested.run',
            eventKwargs: {value: 1},
            policy: proxy._policy,
            state: {loaded: true},
        });
    });

    it('emits before and after listeners around event requests', async () => {
        const proxy = makeProxy({result: {answer: 42}, state: {loaded: true}});
        const before = mock(() => {});
        const after = mock(() => {});

        proxy.addListener('load', before, 'before');
        proxy.addListener('load', after);

        const result = await proxy.load({page: 1});

        expect(result).toEqual({answer: 42});
        expect(proxy._state).toEqual({loaded: true});
        expect(before.mock.calls[0][0].attribute).toBe('GlueBaseProxy.load');
        expect(before.mock.calls[0][0].proxy).toBe(proxy);
        expect(before.mock.calls[0][0].eventKwargs).toEqual({page: 1});
        expect(after.mock.calls[0][0].result).toEqual({answer: 42});
    });

    it('calls the global client message handler when a response includes messages', async () => {
        const onMessage = mock(() => {});
        const proxy = new BaseGlueProxy({
            http: createMockHttp({
                result: {ok: true},
                state: {loaded: true},
                messages: [{level: 25, level_tag: 'success', message: 'Saved', tags: 'success'}],
            }),
            name: 'thing',
            policy: createPolicy('base', {
                bound_attributes: {'GlueBaseProxy.load': {}},
            }),
            state: {loaded: false},
        });
        globalThis.Glue = {_onMessage: onMessage};

        await proxy.load({page: 1});

        expect(onMessage).toHaveBeenCalledTimes(1);
        expect(onMessage.mock.calls[0][0].messages[0].message).toBe('Saved');
        expect(onMessage.mock.calls[0][0].proxy).toBe(proxy);
        expect(onMessage.mock.calls[0][0].attribute).toBe('GlueBaseProxy.load');
        expect(onMessage.mock.calls[0][0].eventKwargs).toEqual({page: 1});
    });

    it('does not call message handlers when messages are missing or empty', async () => {
        const onMessage = mock(() => {});
        const proxy = new BaseGlueProxy({
            http: createMockHttp({result: {ok: true}, state: {loaded: true}, messages: []}),
            name: 'thing',
            policy: createPolicy('base', {
                bound_attributes: {'GlueBaseProxy.load': {}},
            }),
            state: {loaded: false},
        });
        globalThis.Glue = {_onMessage: onMessage};

        await proxy.load();

        expect(onMessage).not.toHaveBeenCalled();
    });

    it('uses proxy-specific message handlers instead of the global handler', async () => {
        const globalOnMessage = mock(() => {});
        const proxyOnMessage = mock(() => {});
        const proxy = new BaseGlueProxy({
            http: createMockHttp({
                result: {ok: true},
                state: {loaded: true},
                messages: [{level: 20, level_tag: 'info', message: 'Proxy message', tags: 'info'}],
            }),
            name: 'thing',
            policy: createPolicy('base', {
                bound_attributes: {'GlueBaseProxy.load': {}},
            }),
            state: {loaded: false},
        });
        globalThis.Glue = {_onMessage: globalOnMessage};

        proxy.onMessage(proxyOnMessage);
        await proxy.load();

        expect(proxyOnMessage).toHaveBeenCalledTimes(1);
        expect(globalOnMessage).not.toHaveBeenCalled();
    });

    it('emits error listeners and rethrows request failures', async () => {
        const error = new Error('network');
        const proxy = makeProxy();
        proxy.http.sendAttributeEventRequest = mock(async () => {
            throw error;
        });
        const onError = mock(() => {});
        proxy.addListener('load', onError, 'error');

        await expect(proxy.load()).rejects.toThrow('network');

        expect(onError.mock.calls[0][0].error).toBe(error);
        expect(proxy._loading).toBe(false);
    });

    it('removes and clears listeners', () => {
        const proxy = makeProxy();
        const listener = () => {};

        proxy.addListener('load', listener);
        proxy.removeListener('load', listener);
        expect(proxy._listeners.after.load).toEqual([]);

        proxy.addListener('load', listener);
        proxy.clearListeners();
        expect(proxy._listeners).toEqual({});
    });

    describe('_handleEventResponse instance_data reactivity', () => {
        it('preserves instance_data object reference when updating values', () => {
            const proxy = makeProxy();
            proxy._state = {
                namespace: 'model',
                instance_data: {id: 1, name: 'Original', age: 25},
                errors: {},
            };
            const originalInstanceData = proxy._state.instance_data;

            proxy._handleEventResponse('save', {}, {
                state: {
                    namespace: 'model',
                    instance_data: {id: 1, name: 'Updated', age: 26},
                    errors: {},
                },
            });

            // The instance_data object reference should be the same
            expect(proxy._state.instance_data).toBe(originalInstanceData);
            // But the values should be updated
            expect(proxy._state.instance_data.name).toBe('Updated');
            expect(proxy._state.instance_data.age).toBe(26);
        });

        it('removes keys from instance_data that are not in the response', () => {
            const proxy = makeProxy();
            proxy._state = {
                namespace: 'model',
                instance_data: {id: 1, name: 'Test', temporaryField: 'should be removed'},
                errors: {},
            };
            const originalInstanceData = proxy._state.instance_data;

            proxy._handleEventResponse('save', {}, {
                state: {
                    namespace: 'model',
                    instance_data: {id: 1, name: 'Test'},
                    errors: {},
                },
            });

            expect(proxy._state.instance_data).toBe(originalInstanceData);
            expect(proxy._state.instance_data.temporaryField).toBeUndefined();
            expect('temporaryField' in proxy._state.instance_data).toBe(false);
        });

        it('adds new keys to instance_data from the response', () => {
            const proxy = makeProxy();
            proxy._state = {
                namespace: 'model',
                instance_data: {id: 1, name: 'Test'},
                errors: {},
            };
            const originalInstanceData = proxy._state.instance_data;

            proxy._handleEventResponse('save', {}, {
                state: {
                    namespace: 'model',
                    instance_data: {id: 1, name: 'Test', newField: 'added'},
                    errors: {},
                },
            });

            expect(proxy._state.instance_data).toBe(originalInstanceData);
            expect(proxy._state.instance_data.newField).toBe('added');
        });

        it('updates other state properties while preserving instance_data reference', () => {
            const proxy = makeProxy();
            proxy._state = {
                namespace: 'model',
                instance_data: {id: 1, name: 'Test'},
                errors: {name: ['Required']},
            };
            const originalInstanceData = proxy._state.instance_data;

            proxy._handleEventResponse('save', {}, {
                state: {
                    namespace: 'model',
                    instance_data: {id: 1, name: 'Test'},
                    errors: {},
                    newProperty: 'added',
                },
            });

            expect(proxy._state.instance_data).toBe(originalInstanceData);
            expect(proxy._state.errors).toEqual({});
            expect(proxy._state.newProperty).toBe('added');
        });

        it('falls back to Object.assign when instance_data does not exist in current state', () => {
            const proxy = makeProxy();
            proxy._state = {namespace: 'model'};

            proxy._handleEventResponse('load', {}, {
                state: {
                    namespace: 'model',
                    instance_data: {id: 1, name: 'New'},
                },
            });

            expect(proxy._state.instance_data).toEqual({id: 1, name: 'New'});
        });

        it('falls back to Object.assign when instance_data does not exist in response', () => {
            const proxy = makeProxy();
            proxy._state = {
                namespace: 'function',
                instance_data: {id: 1},
            };

            proxy._handleEventResponse('execute', {}, {
                state: {
                    namespace: 'function',
                    result: 'success',
                },
            });

            expect(proxy._state.result).toBe('success');
        });
    });
});
