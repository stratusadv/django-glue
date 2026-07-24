import {describe, expect, test} from "bun:test"
import GlueConfig from "../src/config"
import GlueHttp from "../src/http"
import {RelationFieldGlue} from "../src/proxies/fields"
import GlueModelProxy from "../src/proxies/model"
import GlueQuerySetProxy from "../src/proxies/queryset"
import {createPolicy, createMetadata, createState, mockOperationFetch} from "./testUtils"

function http() {
    return new GlueHttp(new GlueConfig())
}

function queryMetadata() {
    return {
        namespace: 'querySet',
        attributes: {
            query_with_params: {namespace: 'callable'},
        },
    }
}

function queryPolicy(name = 'gorillas') {
    return createPolicy({
        name,
        namespace: 'querySet',
        attributes: ['query_with_params'],
    })
}

function modelRow(name, id, values = {}) {
    return {
        policy: createPolicy({
            name,
            attributes: ['id', 'name', 'delete'],
            identity: {target_pk: id, pk_field_name: 'id'},
        }),
        state: createState({instance_data: {id, name, ...values}}),
        metadata: createMetadata({
            attributes: {delete: {namespace: 'callable'}},
        }),
    }
}

function querySet() {
    return new GlueQuerySetProxy({
        http: http(),
        policy: queryPolicy(),
        state: {items: []},
        metadata: queryMetadata(),
    })
}

describe('Glue proxies', () => {
    test('model fields read as primitives and rich fields are exposed through $fields', () => {
        const object = new GlueModelProxy({
            http: http(),
            policy: createPolicy(),
            state: createState(),
            metadata: createMetadata(),
        })
        object._loaded = true

        expect(String(object.name)).toBe('Koko')
        expect(object.name).toBe('Koko')
        expect(object.$fields.name.value).toBe('Koko')
        expect(object.$fields.name.label).toBe('Name')
        expect(object.$fields.birthday.value).toBe('1971-07-04')
        expect(object.$pk).toBe(1)

        object.name = 'Ndume'

        expect(object.name).toBe('Ndume')
        expect(object.$fields.name.value).toBe('Ndume')
    })

    test('attribute responses refresh policy, flat state, and field metadata', async () => {
        mockOperationFetch()
        const object = new GlueModelProxy({
            http: http(),
            policy: createPolicy(),
            state: createState(),
            metadata: createMetadata(),
        })
        object._loaded = true

        await object.save()

        expect(object._policy.original_signature).toBe('next-signature')
        expect(object.name).toBe('Michael')
        expect(object.$fields.birthday.value).toBe('1973-03-01')
    })

    test('dotted callable attributes resolve through container metadata', async () => {
        let capturedAttribute
        global.fetch = async (_url, options) => {
            capturedAttribute = options.body.get('attribute')
            return new Response(JSON.stringify({
                result: {ok: true},
                state: createState(),
                policy: createPolicy({
                    attributes: ['id', 'name', 'services', 'services.increment_age'],
                }),
                metadata: createMetadata({
                    attributes: {
                        services: {namespace: 'container'},
                        'services.increment_age': {namespace: 'callable'},
                    },
                }),
            }), {status: 200, headers: {'Content-Type': 'application/json'}})
        }

        const object = new GlueModelProxy({
            http: http(),
            policy: createPolicy({attributes: ['id', 'services', 'services.increment_age']}),
            state: createState(),
            metadata: createMetadata({
                attributes: {
                    services: {namespace: 'container'},
                    'services.increment_age': {namespace: 'callable'},
                },
            }),
        })

        expect(typeof object.services.increment_age).toBe('function')
        expect(await object.services.increment_age()).toEqual({ok: true})
        expect(capturedAttribute).toBe('services.increment_age')
    })

    test('nested callable responses preserve field proxy identity and state updates', async () => {
        global.fetch = async () => new Response(JSON.stringify({
            result: null,
            state: createState({instance_data: {id: 1, age: 19}}),
            policy: createPolicy({attributes: ['id', 'age', 'services', 'services.increment_age']}),
            metadata: createMetadata({
                fields: {age: {type: 'IntegerField', label: 'Age'}},
                attributes: {
                    services: {namespace: 'container'},
                    'services.increment_age': {namespace: 'callable'},
                },
            }),
        }), {status: 200, headers: {'Content-Type': 'application/json'}})

        const object = new GlueModelProxy({
            http: http(),
            policy: createPolicy({attributes: ['id', 'age', 'services', 'services.increment_age']}),
            state: createState({instance_data: {id: 1, age: 18}}),
            metadata: createMetadata({
                fields: {age: {type: 'IntegerField', label: 'Age'}},
                attributes: {
                    services: {namespace: 'container'},
                    'services.increment_age': {namespace: 'callable'},
                },
            }),
        })
        object._loaded = true
        const field = object.$fields.age

        await object.services.increment_age()

        expect(object.$fields.age).toBe(field)
        expect(object.age).toBe(19)
        expect(field.value).toBe(19)
    })

    test('relation fields lazily load and share choices through the field interface', async () => {
        RelationFieldGlue.loadingCache.clear()
        mockOperationFetch({
            result: [{pk: 1, __str__: 'Grappling'}],
            state: createState({instance_data: {id: 1, skills: []}}),
            policy: createPolicy({attributes: ['id', 'skills', 'foreign_key_choices']}),
            metadata: createMetadata({
                fields: {
                    skills: {
                        type: 'ManyToManyField',
                        label: 'Skills',
                        choices: [],
                        choice_model_path: 'test_project.gorilla.models.Skill',
                        choices_cache_key: 'gorilla.skills',
                    },
                },
                attributes: {foreign_key_choices: {namespace: 'callable'}},
            }),
        })
        const object = new GlueModelProxy({
            http: http(),
            policy: createPolicy({attributes: ['id', 'skills', 'foreign_key_choices']}),
            state: createState({instance_data: {id: 1, skills: []}}),
            metadata: createMetadata({
                fields: {
                    skills: {
                        type: 'ManyToManyField',
                        label: 'Skills',
                        choices: [],
                        choice_model_path: 'test_project.gorilla.models.Skill',
                        choices_cache_key: 'gorilla.skills',
                    },
                },
                attributes: {foreign_key_choices: {namespace: 'callable'}},
            }),
        })
        object._loaded = true

        expect(object.$fields.skills.choices).toEqual([])
        await new Promise(resolve => setTimeout(resolve, 0))

        expect(object.$fields.skills.choices).toEqual([{pk: 1, __str__: 'Grappling'}])
        object.$fields.skills.value = [{pk: 1, __str__: 'Grappling'}]
        expect(object.$fields.skills.selectedPks).toEqual([1])
        expect(object.$fields.skills.has(1)).toBe(true)
    })

    test('querysets build model proxies from returned row manifests', async () => {
        const object = querySet()
        const rows = [modelRow('gorillas.1', 1), modelRow('gorillas.2', 2)]
        global.fetch = async () => new Response(JSON.stringify({
            result: {items: rows},
            state: {items: []},
            policy: queryPolicy(),
            metadata: queryMetadata(),
        }), {status: 200, headers: {'Content-Type': 'application/json'}})

        const filtered = await object.filter({name__icontains: 'ko'}).all()

        expect(filtered.items).toHaveLength(2)
        expect(filtered.items[0]).toBeInstanceOf(GlueModelProxy)
        expect(filtered.items[0].name).toBe('gorillas.1')
    })

    test('querysets merge chained query parameters before all executes', async () => {
        const object = querySet()
        let kwargs
        global.fetch = async (_url, options) => {
            kwargs = JSON.parse(options.body.get('kwargs'))
            return new Response(JSON.stringify({
                result: {items: []},
                state: {items: []},
                policy: queryPolicy(),
                metadata: queryMetadata(),
            }), {status: 200, headers: {'Content-Type': 'application/json'}})
        }

        await object
            .filter({name__icontains: 'ko'})
            .orderBy('name')
            .slice(0, 10)
            .all()

        expect(kwargs).toEqual({
            filter: {name__icontains: 'ko'},
            order_by: 'name',
            slice: {start: 0, stop: 10},
        })
    })
})
