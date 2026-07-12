import {describe, expect, it, mock} from 'bun:test';
import GlueQuerySetProxy from '../../src/proxies/queryset';
import GlueModelProxy from '../../src/proxies/model';
import {createMockHttp, createModelPolicy, createQuerySetPolicy} from '../testUtils';

describe('GlueQuerySetProxy', () => {
    function modelItem(id, name) {
        return {
            id,
            name,
            __policy__: createModelPolicy({
                subject_details: {target_pk: id},
            }),
        };
    }

    function makeQuerySet(responseState = {list_data: [modelItem(1, 'Koko')]}) {
        globalThis.Glue = {model: {}};
        return new GlueQuerySetProxy({
            http: createMockHttp({result: {}, state: responseState}),
            name: 'gorillas',
            policy: createQuerySetPolicy(),
            state: {list_data: []},
        });
    }

    it('queries with params and builds child model proxies from state data', async () => {
        const proxy = makeQuerySet();
        const items = await proxy.queryWithParams({filter: {name: 'Koko'}});

        expect(items).toHaveLength(1);
        expect(items[0]).toBeInstanceOf(GlueModelProxy);
        expect(items[0].name).toBe('Koko');
        expect(proxy.http.sendAttributeEventRequest.mock.calls[0][0].attribute).toBe(
            'GlueQuerySetProxy.query_with_params',
        );
    });

    it('caches identical query params after loading', async () => {
        const proxy = makeQuerySet();

        await proxy.queryWithParams({filter: {name: 'Koko'}});
        await proxy.queryWithParams({filter: {name: 'Koko'}});

        expect(proxy.http.sendAttributeEventRequest).toHaveBeenCalledTimes(1);
    });

    it('updates query params through filter, ordering, and slicing helpers', () => {
        const proxy = makeQuerySet();

        expect(proxy.filter({age__gt: 10})).toBe(proxy);
        expect(proxy.orderBy('-name')).toBe(proxy);
        expect(proxy.sliceStart(0)).toBe(proxy);
        expect(proxy.sliceEnd(10)).toBe(proxy);
        expect(proxy.slice(0, 5)).toBe(proxy);

        expect(proxy._queryParams).toEqual({
            filter: {age__gt: 10},
            order_by: '-name',
            slice: {start: 0, stop: 5},
        });
    });

    it('pushes new model instances at the requested location', async () => {
        const proxy = makeQuerySet();
        proxy.http = createMockHttp({
            result: modelItem(2, 'New'),
            state: {list_data: []},
        });

        await proxy.pushNew('end');

        expect(proxy.http.sendAttributeEventRequest.mock.calls[0][0].attribute).toBe(
            'GlueQuerySetProxy.new',
        );
        expect(proxy._items).toHaveLength(1);
        expect(proxy._items[0].name).toBe('New');
    });

    it('prepends new model instances by default and through prependNew', async () => {
        const proxy = makeQuerySet();
        proxy.http = createMockHttp({
            result: modelItem(3, 'First'),
            state: {list_data: []},
        });

        await proxy.pushNew();
        expect(proxy._items.map(item => item.name)).toEqual(['First']);

        proxy.http = createMockHttp({
            result: modelItem(4, 'Before First'),
            state: {list_data: []},
        });
        await proxy.prependNew();

        expect(proxy._items.map(item => item.name)).toEqual(['Before First']);
    });

    it('appendNew appends model instances', async () => {
        const proxy = makeQuerySet();
        proxy.http = createMockHttp({
            result: modelItem(5, 'Last'),
            state: {list_data: []},
        });

        await proxy.appendNew();

        expect(proxy._items.map(item => item.name)).toEqual(['Last']);
    });

    it('throws for invalid pushNew locations', async () => {
        const proxy = makeQuerySet();
        proxy.http = createMockHttp({
            result: modelItem(6, 'Invalid'),
            state: {list_data: []},
        });

        await expect(proxy.pushNew('middle')).rejects.toThrow('Invalid location');
    });

    it('throws when child model data is missing policy metadata', () => {
        const proxy = makeQuerySet();

        expect(() => proxy.buildChildModelProxy({id: 1, name: 'No Policy'}))
            .toThrow('Child proxy item missing __policy__ for pk 1');
    });

    it('uses child policy name when building model proxies', () => {
        const proxy = makeQuerySet();
        const child = proxy.buildChildModelProxy({
            id: null,
            name: '',
            __policy__: {
                ...createModelPolicy({subject_details: {target_pk: null}}),
                name: 'gorillas__None',
            },
        });

        expect(child._name).toBe('gorillas__None');
        expect(globalThis.Glue.model.gorillas__None).toBe(child);
    });

    it('is iterable over loaded items', async () => {
        const proxy = makeQuerySet();
        await proxy.all();

        expect([...proxy].map(item => item.name)).toEqual(['Koko']);
        expect(proxy.isLoaded).toBe(true);
        expect(proxy.isEmpty).toBe(false);
    });

    it('forwards child model save and delete events to queryset listeners', async () => {
        const proxy = makeQuerySet();
        const onSave = mock(() => {});
        const onDelete = mock(() => {});
        proxy.addListener('save', onSave);
        proxy.addListener('delete', onDelete);

        await proxy.all();
        const child = proxy._items[0];
        child.http = createMockHttp({result: {saved: true}, state: child._state});

        await child.save();
        await child.delete();

        expect(onSave.mock.calls[0][0].proxy).toBe(child);
        expect(onSave.mock.calls[0][0].result).toEqual({saved: true});
        expect(onDelete.mock.calls[0][0].proxy).toBe(child);
    });

    it('forwards child model save and delete errors to queryset listeners', async () => {
        const proxy = makeQuerySet();
        const onSaveError = mock(() => {});
        const onDeleteError = mock(() => {});
        proxy.addListener('save', onSaveError, 'error');
        proxy.addListener('delete', onDeleteError, 'error');

        await proxy.all();
        const child = proxy._items[0];
        child.http.sendAttributeEventRequest = mock(async () => {
            throw new Error('failed');
        });

        await expect(child.save()).rejects.toThrow('failed');
        await expect(child.delete()).rejects.toThrow('failed');

        expect(onSaveError.mock.calls[0][0].proxy).toBe(child);
        expect(onDeleteError.mock.calls[0][0].proxy).toBe(child);
    });

    it('shares ModelChoiceField choices cache across multiple child proxies', async () => {
        // Create a queryset with multiple items that have a ModelChoiceField
        const choicesResponse = [
            {pk: 1, __str__: 'Skill A'},
            {pk: 2, __str__: 'Skill B'},
            {pk: 3, __str__: 'Skill C'},
        ];

        function modelItemWithSkills(id, name, skills = []) {
            return {
                id,
                name,
                skills,
                __policy__: createModelPolicy({
                    subject_details: {
                        target_pk: id,
                        included_fields: {
                            id: {type: 'IntegerField', label: 'ID'},
                            name: {type: 'CharField', label: 'Name'},
                            skills: {type: 'ModelMultipleChoiceField', label: 'Skills'},
                        },
                    },
                    bound_attributes: {
                        'GlueModelInstanceProxy.save': {},
                        'GlueModelInstanceProxy.delete': {},
                        'GlueFormProxy.foreign_key_choices': {},
                    },
                }),
            };
        }

        globalThis.Glue = {model: {}};

        // Track how many times foreign_key_choices is called
        let choicesCallCount = 0;
        const mockHttp = {
            sendAttributeEventRequest: mock(async (params) => {
                if (params.attribute === 'GlueFormProxy.foreign_key_choices') {
                    choicesCallCount++;
                    return {data: {result: choicesResponse, state: params.state}};
                }
                return {data: {result: {}, state: {
                    list_data: [
                        modelItemWithSkills(1, 'Gorilla 1', [{pk: 1, __str__: 'Skill A'}]),
                        modelItemWithSkills(2, 'Gorilla 2', [{pk: 2, __str__: 'Skill B'}]),
                        modelItemWithSkills(3, 'Gorilla 3', [{pk: 1, __str__: 'Skill A'}, {pk: 3, __str__: 'Skill C'}]),
                    ],
                }}};
            }),
        };

        const proxy = new GlueQuerySetProxy({
            http: mockHttp,
            name: 'gorillas',
            policy: createQuerySetPolicy({
                subject_details: {
                    included_fields: {
                        skills: {type: 'ModelMultipleChoiceField', label: 'Skills'},
                    },
                },
            }),
            state: {list_data: []},
        });

        // Query to get all items
        const items = await proxy.queryWithParams();
        expect(items).toHaveLength(3);

        // Access choices on all three items - should only trigger ONE request
        const choices1 = items[0].$fields.skills.choices;
        const choices2 = items[1].$fields.skills.choices;
        const choices3 = items[2].$fields.skills.choices;

        // Wait for async choices to load
        await new Promise(resolve => setTimeout(resolve, 0));

        // Re-access choices after loading
        const loadedChoices1 = items[0].$fields.skills.choices;
        const loadedChoices2 = items[1].$fields.skills.choices;
        const loadedChoices3 = items[2].$fields.skills.choices;

        // All should have the same choices data
        expect(loadedChoices1).toHaveLength(3);
        expect(loadedChoices2).toHaveLength(3);
        expect(loadedChoices3).toHaveLength(3);

        // All should reference the same array (from cache)
        expect(loadedChoices1).toBe(loadedChoices2);
        expect(loadedChoices2).toBe(loadedChoices3);

        // Should only have made ONE foreign_key_choices request (cached for others)
        expect(choicesCallCount).toBe(1);
    });
});
