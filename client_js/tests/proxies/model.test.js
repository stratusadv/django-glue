import {describe, expect, it, mock} from 'bun:test';
import GlueModelProxy from '../../src/proxies/model';
import {createMockHttp, createModelPolicy, createState} from '../testUtils';

describe('GlueModelProxy', () => {
    function makeModel({policy = createModelPolicy(), state = createState({id: 1, name: 'Koko'})} = {}) {
        return new GlueModelProxy({
            http: createMockHttp({result: {}, state}),
            name: 'gorilla',
            policy,
            state,
        });
    }

    it('extends form field behavior and exposes primary key state', () => {
        const proxy = makeModel();

        expect(proxy.name).toBe('Koko');
        expect(proxy.pk).toBe(1);
        expect(proxy._isNew).toBe(false);
        expect(proxy.$key).toStartWith('django-glue-');
    });

    it('treats models without a pk as new', () => {
        const proxy = makeModel({
            policy: createModelPolicy({subject_details: {target_pk: null}}),
            state: createState({name: 'Unsaved'}),
        });

        expect(proxy.pk).toBeUndefined();
        expect(proxy._isNew).toBe(true);
    });

    it('defines extra fields returned by the server', () => {
        const proxy = makeModel({state: createState({id: 1, name: 'Koko', score: 99})});

        expect(proxy.score).toBe(99);
        proxy.score = 100;
        expect(proxy._state.instance_data.score).toBe(100);
    });

    it('refreshes parent queryset after state-changing events', () => {
        const parent = {refresh: mock(() => {})};
        const proxy = new GlueModelProxy({
            http: createMockHttp({result: {}, state: createState({id: 1, name: 'Koko'})}),
            name: 'gorilla',
            policy: createModelPolicy(),
            state: createState({id: 1, name: 'Koko'}),
            parentQuerySet: parent,
        });

        proxy._handleEventResponse('GlueModelProxy.save', {}, {state: proxy._state});

        expect(parent.refresh).toHaveBeenCalled();
    });
});
