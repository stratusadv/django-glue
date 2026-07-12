import {beforeEach, describe, expect, it, mock} from 'bun:test';
import GlueFormProxy from '../../src/proxies/form';
import {createFormPolicy, createMockHttp, createState} from '../testUtils';

describe('GlueFormProxy', () => {
    beforeEach(() => {
        GlueFormProxy.choicesCache.clear();
    });

    function makeForm({policy = createFormPolicy(), state = createState({name: 'Ada'})} = {}) {
        return new GlueFormProxy({
            http: createMockHttp({result: {valid: true}, state}),
            name: 'contact',
            policy,
            state,
        });
    }

    it('defines field accessors from policy field metadata', () => {
        const proxy = makeForm();

        expect(proxy.name).toBe('Ada');
        proxy.email = 'ada@example.com';

        expect(proxy._state.instance_data.email).toBe('ada@example.com');
        expect(proxy.$fields.name.name).toBe('name');
    });

    it('loads state instance data into field values', () => {
        const proxy = makeForm({state: createState({name: 'Ada', email: 'ada@example.com'})});

        proxy.loadInstanceData();

        expect(proxy.$fields.name.value).toBe('Ada');
        expect(proxy.$fields.email.value).toBe('ada@example.com');
        expect(proxy._loaded).toBe(true);
    });

    it('reports validation errors from state', () => {
        const proxy = makeForm({
            state: {
                instance_data: {name: ''},
                errors: {name: ['Required']},
            },
        });

        expect(proxy.hasErrors()).toBe(true);
        expect(proxy.hasErrors('name')).toBe(true);
        expect(proxy.hasErrors('email')).toBe(false);
        expect(proxy.$fields.name.hasErrors).toBe(true);
    });

    it('refreshes field error metadata after event responses', () => {
        const proxy = makeForm({state: createState({name: 'Ada'})});

        proxy._handleEventResponse(
            'GlueFormProxy.save',
            null,
            {
                result: null,
                state: {
                    instance_data: {name: 'Ada'},
                    errors: {name: ['Required']},
                },
            },
        );

        expect(proxy.$fields.name.hasErrors).toBe(true);
        expect(proxy.$fields.name.errorText).toBe('Required');

        proxy._handleEventResponse(
            'GlueFormProxy.save',
            null,
            {
                result: null,
                state: {
                    instance_data: {name: 'Ada'},
                    errors: {},
                },
            },
        );

        expect(proxy.$fields.name.hasErrors).toBe(false);
        expect(proxy.$fields.name.errorText).toBeUndefined();
    });

    it('updates field choices from foreign key choice responses', () => {
        const policy = createFormPolicy({
            subject_details: {
                included_fields: {
                    owner: {type: 'ModelChoiceField', label: 'Owner'},
                },
            },
        });
        const proxy = makeForm({policy, state: createState({owner: null})});

        proxy._handleEventResponse(
            'foreign_key_choices',
            {field_name: 'owner'},
            {result: [{pk: 1, __str__: 'Jane'}], state: proxy._state},
        );

        // choices is a getter property that returns the choices array
        expect(proxy.$fields.owner.choices).toEqual([{pk: 1, __str__: 'Jane'}]);
    });

    describe('ModelChoiceField choices', () => {
        function makeFormWithChoiceField() {
            const policy = createFormPolicy({
                subject_details: {
                    included_fields: {
                        category: {type: 'ModelChoiceField', label: 'Category'},
                    },
                },
            });
            return makeForm({policy, state: createState({category: null})});
        }

        it('initializes choices as empty array before loading', () => {
            const proxy = makeFormWithChoiceField();
            // Mark as already loading to prevent trigger, so we can test initial state
            proxy.$fields.category.__glue__loadingChoices = true;
            expect(proxy.$fields.category.choices).toEqual([]);
        });

        it('populates choices when response is received via _handleEventResponse', () => {
            const proxy = makeFormWithChoiceField();

            // Simulate response from server
            proxy._handleEventResponse(
                'foreign_key_choices',
                {field_name: 'category'},
                {
                    result: [
                        {pk: 1, __str__: 'Tech'},
                        {pk: 2, __str__: 'Sports'},
                        {pk: 3, __str__: 'Music'},
                    ],
                    state: proxy._state,
                },
            );

            expect(proxy.$fields.category.choices).toEqual([
                {pk: 1, __str__: 'Tech'},
                {pk: 2, __str__: 'Sports'},
                {pk: 3, __str__: 'Music'},
            ]);
        });

        it('returns consistent choices data on multiple accesses', () => {
            const proxy = makeFormWithChoiceField();

            // Simulate response
            proxy._handleEventResponse(
                'foreign_key_choices',
                {field_name: 'category'},
                {result: [{pk: 1, __str__: 'Tech'}, {pk: 2, __str__: 'Sports'}], state: proxy._state},
            );

            // Access choices multiple times
            const choices1 = proxy.$fields.category.choices;
            const choices2 = proxy.$fields.category.choices;
            const choices3 = proxy.$fields.category.choices;

            // All should return the same data
            expect(choices1).toEqual([{pk: 1, __str__: 'Tech'}, {pk: 2, __str__: 'Sports'}]);
            expect(choices2).toEqual([{pk: 1, __str__: 'Tech'}, {pk: 2, __str__: 'Sports'}]);
            expect(choices3).toEqual([{pk: 1, __str__: 'Tech'}, {pk: 2, __str__: 'Sports'}]);
        });

        it('handles empty choices response', () => {
            const proxy = makeFormWithChoiceField();

            proxy._handleEventResponse(
                'foreign_key_choices',
                {field_name: 'category'},
                {result: [], state: proxy._state},
            );

            expect(proxy.$fields.category.choices).toEqual([]);
        });

        it('loads choices lazily on first choices access', async () => {
            const proxy = makeFormWithChoiceField();
            proxy.http = createMockHttp({
                result: [{pk: 1, __str__: 'Lazy'}],
                state: proxy._state,
            });

            expect(proxy.$fields.category.choices).toEqual([]);
            await new Promise(resolve => setTimeout(resolve, 0));

            expect(proxy.http.sendAttributeEventRequest.mock.calls[0][0].attribute).toBe(
                'GlueFormProxy.foreign_key_choices',
            );
            expect(proxy.$fields.category.choices).toEqual([{pk: 1, __str__: 'Lazy'}]);
        });

        it('does not start another lazy choices request while loading or loaded', async () => {
            const proxy = makeFormWithChoiceField();
            const field = proxy.$fields.category;

            field.__glue__loadingChoices = true;
            await proxy._loadFieldChoices('category', field);
            expect(proxy.http.sendAttributeEventRequest).not.toHaveBeenCalled();

            field.__glue__loadingChoices = false;
            field.__glue__choicesLoaded = true;
            await proxy._loadFieldChoices('category', field);
            expect(proxy.http.sendAttributeEventRequest).not.toHaveBeenCalled();
        });

        it('sets choices when the backing choices array is missing', () => {
            const proxy = makeFormWithChoiceField();
            delete proxy.$fields.category.__glue__choicesData;

            proxy._setFieldChoices('category', [{pk: 1, __str__: 'A'}]);

            expect(proxy.$fields.category.choices).toEqual([{pk: 1, __str__: 'A'}]);
        });

        it('ignores choice updates for missing fields', () => {
            const proxy = makeFormWithChoiceField();

            expect(() => proxy._setFieldChoices('missing', [{pk: 1, __str__: 'A'}])).not.toThrow();
        });

        it('correctly identifies ModelChoiceField type', () => {
            const proxy = makeFormWithChoiceField();
            expect(proxy.$fields.category.type).toBe('ModelChoiceField');
        });

        it('sets up choices data structure for ModelMultipleChoiceField', () => {
            const policy = createFormPolicy({
                subject_details: {
                    included_fields: {
                        skills: {type: 'ModelMultipleChoiceField', label: 'Skills'},
                    },
                },
            });
            const proxy = makeForm({policy, state: createState({skills: []})});

            // Simulate response
            proxy._handleEventResponse(
                'foreign_key_choices',
                {field_name: 'skills'},
                {result: [{pk: 1, __str__: 'Skill A'}, {pk: 2, __str__: 'Skill B'}], state: proxy._state},
            );

            expect(proxy.$fields.skills.choices).toEqual([
                {pk: 1, __str__: 'Skill A'},
                {pk: 2, __str__: 'Skill B'},
            ]);
        });

        it('initializes missing ModelMultipleChoiceField values as an empty array', () => {
            const policy = createFormPolicy({
                subject_details: {
                    included_fields: {
                        skills: {type: 'ModelMultipleChoiceField', label: 'Skills'},
                    },
                },
            });

            const missing = makeForm({policy, state: createState({})});
            const nullValue = makeForm({policy, state: createState({skills: null})});

            expect(missing.skills).toEqual([]);
            expect(nullValue.skills).toEqual([]);
            expect(Array.isArray(missing.$fields.skills.value)).toBe(true);
            expect(Array.isArray(nullValue.$fields.skills.value)).toBe(true);
        });

        it('shares lazy choice requests across matching fields', async () => {
            const policy = createFormPolicy({
                subject_details: {
                    model_class_path: 'test_project.gorilla.models.Gorilla',
                    included_fields: {
                        skills: {
                            type: 'ModelMultipleChoiceField',
                            label: 'Skills',
                            choices_cache_key: 'gorilla.skills',
                        },
                    },
                },
            });
            const http = createMockHttp({
                result: [{pk: 1, __str__: 'Skill A'}],
                state: createState({skills: []}),
            });
            const first = makeForm({policy, state: createState({skills: []})});
            const second = makeForm({policy, state: createState({skills: []})});
            first.http = http;
            second.http = http;

            expect(first.$fields.skills.choices).toEqual([]);
            expect(second.$fields.skills.choices).toEqual([]);
            await new Promise(resolve => setTimeout(resolve, 0));

            expect(http.sendAttributeEventRequest).toHaveBeenCalledTimes(1);
            expect(first.$fields.skills.choices).toEqual([{pk: 1, __str__: 'Skill A'}]);
            expect(second.$fields.skills.choices).toEqual([{pk: 1, __str__: 'Skill A'}]);
        });

        it('enriches the shared choices cache with buildChoices fields', async () => {
            const proxy = makeFormWithChoiceField();
            proxy.http = {
                sendAttributeEventRequest: mock(async ({eventKwargs}) => ({
                    data: {
                        result: eventKwargs.choice_fields?.includes('rank_points')
                            ? [{pk: 1, __str__: 'Koko', rank_points: 200}]
                            : [{pk: 1, __str__: 'Koko'}],
                        state: proxy._state,
                    },
                })),
            };

            const defaultChoices = proxy.$fields.category.choices;
            await new Promise(resolve => setTimeout(resolve, 0));
            const enrichedChoices = proxy.$fields.category.buildChoices('rank_points');
            await new Promise(resolve => setTimeout(resolve, 0));

            expect(enrichedChoices).toBe(defaultChoices);
            expect(proxy.$fields.category.choices).toEqual([
                {pk: 1, __str__: 'Koko', rank_points: 200},
            ]);
            expect(proxy.http.sendAttributeEventRequest.mock.calls[1][0].eventKwargs).toEqual({
                field_name: 'category',
                choice_fields: ['rank_points'],
            });
        });
    });

    it('processes validate and save bound attributes through the base event path', async () => {
        const state = createState({name: 'Ada'});
        const proxy = makeForm({state});

        await proxy.validate();
        await proxy.save();

        expect(proxy.http.sendAttributeEventRequest.mock.calls[0][0].attribute).toBe('GlueFormProxy.validate');
        expect(proxy.http.sendAttributeEventRequest.mock.calls[1][0].attribute).toBe('GlueFormProxy.save');
    });

    it('creates instance_data when setting field values on an empty state', () => {
        const proxy = makeForm({state: {errors: {}}});

        proxy.name = 'Ada';
        proxy.$fields.email.value = 'ada@example.com';

        expect(proxy._state.instance_data).toEqual({
            name: 'Ada',
            email: 'ada@example.com',
        });
    });

    it('submits model choice objects without mutating them on the client', async () => {
        const policy = createFormPolicy({
            subject_details: {
                included_fields: {
                    owner: {type: 'ModelChoiceField', label: 'Owner', pk_field: 'id'},
                    skills: {type: 'ModelMultipleChoiceField', label: 'Skills', pk_field: 'id'},
                },
            },
        });
        const state = createState({
            owner: {pk: 7, __str__: 'Jane'},
            skills: [{pk: 1, __str__: 'Skill A'}],
        });
        const proxy = makeForm({policy, state});

        await proxy.save();

        const submittedState = proxy.http.sendAttributeEventRequest.mock.calls[0][0].state;
        expect(submittedState.instance_data.owner).toEqual({pk: 7, __str__: 'Jane'});
        expect(submittedState.instance_data.skills).toEqual([{pk: 1, __str__: 'Skill A'}]);
        expect(proxy._state.instance_data.owner).toEqual({pk: 7, __str__: 'Jane'});
        expect(proxy._state.instance_data.skills).toEqual([{pk: 1, __str__: 'Skill A'}]);
    });
});
