import {describe, expect, test} from "bun:test"
import GlueConfig from "../src/config"
import GlueHttp from "../src/http"
import {RelationFieldGlue} from "../src/proxies/fields"
import GlueFormProxy from "../src/proxies/form"
import GlueJsonProxy from "../src/proxies/json"
import GlueModelProxy from "../src/proxies/model"
import GlueQuerySetProxy from "../src/proxies/queryset"
import {registerProxyClass} from "../src/proxies/registry"
import {createPolicy, createMetadata, createState, mockOperationFetch} from "./testUtils"

function http() {
    return new GlueHttp(new GlueConfig())
}

function queryMetadata() {
    return {
        namespace: 'querySet',
        attributes: {
            get: {namespace: 'callable'},
            query_with_params: {namespace: 'callable'},
        },
    }
}

function queryPolicy(name = 'gorillas') {
    return createPolicy({
        name,
        namespace: 'querySet',
        attributes: ['get', 'query_with_params'],
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
    test('json proxy exposes policy identity value', () => {
        const object = new GlueJsonProxy({
            http: http(),
            policy: createPolicy({
                name: 'permission_data',
                namespace: 'json',
                identity: {
                    value: [
                        {group: 'admin', permissions: ['auth.add_group']},
                    ],
                },
                attributes: [],
            }),
            metadata: {namespace: 'json', type: 'array', attributes: {}},
        })

        expect(object.value).toEqual([
            {group: 'admin', permissions: ['auth.add_group']},
        ])
        expect(object.length).toBe(1)
        expect(object.at(0).group).toBe('admin')
        expect([...object]).toEqual(object.value)
    })

    test('glue object attributes initialize nested form proxies', () => {
        registerProxyClass('form', GlueFormProxy)
        const formPolicy = createPolicy({
            name: 'gorilla.forms.default',
            namespace: 'form',
            attributes: ['name', 'validate'],
        })
        const formMetadata = {
            namespace: 'form',
            attributes: {
                name: {namespace: 'field', type: 'CharField'},
                validate: {namespace: 'callable'},
            },
        }
        // Nested policies are now objects in policy.attributes
        // State keys use relative names (without parent prefix)
        const object = new GlueModelProxy({
            http: http(),
            policy: createPolicy({attributes: [
                'id',
                'forms',
                formPolicy,  // nested policy for forms.default
            ]}),
            state: {
                id: {value: 1},
                'forms.default': {name: {value: 'Koko'}},
            },
            metadata: createMetadata({
                attributes: {
                    id: {namespace: 'field', type: 'IntegerField'},
                    forms: {namespace: 'composite'},
                    // 'form' is an alias - name points to the target
                    form: {
                        name: 'forms.default',
                        namespace: 'glue',
                        glue_namespace: 'form',
                        metadata: formMetadata,
                    },
                    'forms.default': {
                        namespace: 'glue',
                        glue_namespace: 'form',
                        metadata: formMetadata,
                    },
                },
            }),
        })

        expect(object.forms.default).toBeInstanceOf(GlueFormProxy)
        expect(object.form).toBeInstanceOf(GlueFormProxy)
        expect(object.forms.default).toBe(object.form)
        expect(object.form.name).toBe('Koko')
    })

    test('glue object attributes initialize named nested form proxies', () => {
        registerProxyClass('form', GlueFormProxy)
        const formPolicy = createPolicy({
            name: 'gorilla.forms.edit',
            namespace: 'form',
            attributes: ['name'],
        })
        const formMetadata = {
            namespace: 'form',
            attributes: {
                name: {namespace: 'field', type: 'CharField'},
            },
        }
        // Nested policies are now objects in policy.attributes
        // State keys use relative names (without parent prefix)
        const object = new GlueModelProxy({
            http: http(),
            policy: createPolicy({attributes: [
                'id',
                'forms',
                formPolicy,  // nested policy for forms.edit
            ]}),
            state: {
                id: {value: 1},
                'forms.edit': {name: {value: 'Ndume'}},
            },
            metadata: createMetadata({
                attributes: {
                    id: {namespace: 'field', type: 'IntegerField'},
                    forms: {namespace: 'composite'},
                    'forms.edit': {
                        namespace: 'glue',
                        glue_namespace: 'form',
                        metadata: formMetadata,
                    },
                },
            }),
        })

        expect(object.forms.edit).toBeInstanceOf(GlueFormProxy)
        expect(object.forms.edit.name).toBe('Ndume')
    })

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

    test('field proxy value access triggers lazy loading', async () => {
        let loadCalled = false
        global.fetch = async (_url, options) => {
            loadCalled = options.body.get('attribute') === 'load'
            return new Response(JSON.stringify({
                result: {state: {groups: {value: [1], errors: []}}},
                state: {groups: {value: [1], errors: []}},
                policy: createPolicy({
                    name: 'group_form',
                    namespace: 'form',
                    attributes: ['groups', 'load'],
                }),
                metadata: {
                    namespace: 'form',
                    attributes: {
                        groups: {
                            namespace: 'field',
                            type: 'ModelMultipleChoiceField',
                            choices: [],
                            choice_model_path: 'django_spire.auth.group.models.AuthGroup',
                        },
                        load: {namespace: 'callable'},
                    },
                },
            }), {status: 200, headers: {'Content-Type': 'application/json'}})
        }
        const form = new GlueFormProxy({
            http: http(),
            policy: createPolicy({
                name: 'group_form',
                namespace: 'form',
                attributes: ['groups', 'load'],
            }),
            metadata: {
                namespace: 'form',
                attributes: {
                    groups: {
                        namespace: 'field',
                        type: 'ModelMultipleChoiceField',
                        choices: [],
                        choice_model_path: 'django_spire.auth.group.models.AuthGroup',
                    },
                    load: {namespace: 'callable'},
                },
            },
        })

        expect(form.$fields.groups.hasChoiceSelected(1)).toBe(false)
        expect(loadCalled).toBe(true)
        await new Promise(resolve => setTimeout(resolve, 0))

        expect(form.$fields.groups.hasChoiceSelected(1)).toBe(true)
    })

    test('listeners can be removed', async () => {
        mockOperationFetch()
        const object = new GlueModelProxy({
            http: http(),
            policy: createPolicy(),
            state: createState(),
            metadata: createMetadata(),
        })
        let callCount = 0
        const listener = () => {
            callCount += 1
        }

        object.addListener('save', listener)
        object.removeListener('save', listener)
        await object.save()

        expect(callCount).toBe(0)
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

    test('dotted callable attributes resolve through composite metadata', async () => {
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
                        services: {namespace: 'composite'},
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
                    services: {namespace: 'composite'},
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
                    services: {namespace: 'composite'},
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
                    services: {namespace: 'composite'},
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
            result: [{value: 1, label: 'Grappling', obj: {pk: 1, __str__: 'Grappling'}}],
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

        expect(object.$fields.skills.choices).toEqual([
            {value: 1, label: 'Grappling', obj: {pk: 1, __str__: 'Grappling'}},
        ])
        object.$fields.skills.value = [1]
        expect(object.$fields.skills.selectedPks).toEqual([1])
        expect(object.$fields.skills.hasChoiceSelected(1)).toBe(true)
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

    test('querysets expose computed annotations on returned model proxies', async () => {
        const object = querySet()
        const rows = [{
            policy: createPolicy({
                name: 'gorillas.1',
                attributes: ['id', 'name', 'badge_data'],
                identity: {target_pk: 1, pk_field_name: 'id'},
            }),
            state: createState({
                instance_data: {
                    id: 1,
                    name: 'Koko',
                    badge_data: {label: 'KOKO'},
                },
            }),
            metadata: createMetadata({
                attributes: {
                    badge_data: {namespace: 'readonly'},
                },
            }),
        }]
        global.fetch = async () => new Response(JSON.stringify({
            result: {items: rows},
            state: {items: []},
            policy: queryPolicy(),
            metadata: queryMetadata(),
        }), {status: 200, headers: {'Content-Type': 'application/json'}})

        const filtered = await object.all()

        expect(filtered.items[0].badge_data).toEqual({label: 'KOKO'})
    })

    test('querysets get one model proxy by pk', async () => {
        const object = querySet()
        let attribute
        let kwargs
        global.fetch = async (_url, options) => {
            attribute = options.body.get('attribute')
            kwargs = JSON.parse(options.body.get('kwargs'))
            return new Response(JSON.stringify({
                result: modelRow('gorillas.3', 3),
                state: {},
                policy: queryPolicy(),
                metadata: queryMetadata(),
            }), {status: 200, headers: {'Content-Type': 'application/json'}})
        }

        const item = await object.get(3)

        expect(attribute).toBe('get')
        expect(kwargs).toEqual({pk: 3})
        expect(item).toBeInstanceOf(GlueModelProxy)
        expect(item.$collection).toBe(object)
        expect(item.name).toBe('gorillas.3')
    })

    test('querysets get updates an existing cached model proxy in place', async () => {
        const object = querySet()
        const originalRows = [modelRow('gorillas.3', 3, {name: 'Original'})]
        global.fetch = async () => new Response(JSON.stringify({
            result: {items: originalRows},
            state: {},
            policy: queryPolicy(),
            metadata: queryMetadata(),
        }), {status: 200, headers: {'Content-Type': 'application/json'}})
        await object.all()
        const originalItem = object.items[0]

        global.fetch = async () => new Response(JSON.stringify({
            result: modelRow('gorillas.3', 3, {name: 'Updated'}),
            state: {},
            policy: queryPolicy(),
            metadata: queryMetadata(),
        }), {status: 200, headers: {'Content-Type': 'application/json'}})

        const reloadedItem = await object.get(3)

        expect(reloadedItem).toBe(originalItem)
        expect(originalItem.name).toBe('Updated')
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

describe('Foreign key proxy handling', () => {
    test('eager FK creates nested proxy with loaded state', () => {
        registerProxyClass('model', GlueModelProxy)

        // Parent model state (nested in the child's state)
        const parentState = {
            id: {value: 1, errors: []},
            name: {value: 'Parent Task', errors: []},
        }

        // Child model with eager-loaded parent
        // Note: When FK has a value, the nested policy REPLACES 'parent' string in attributes
        const childPolicy = createPolicy({
            name: 'child',
            namespace: 'model',
            attributes: [
                'id',
                'title',
                'parent_id',
                // Nested policy replaces 'parent' string
                createPolicy({
                    name: 'child.parent',
                    namespace: 'model',
                    attributes: ['id', 'name', 'load'],
                    identity: {target_pk: 1, pk_field_name: 'id'},
                }),
            ],
            identity: {target_pk: 2, pk_field_name: 'id'},
        })

        const childMetadata = createMetadata({
            attributes: {
                id: {namespace: 'field', type: 'IntegerField'},
                title: {namespace: 'field', type: 'CharField'},
                parent_id: {namespace: 'field', type: 'IntegerField'},
                parent: {
                    namespace: 'related_field',
                    lazy: false,
                    fk_attname: 'parent_id',
                    pk_field: 'id',
                    glue_namespace: 'model',
                    metadata: {
                        attributes: {
                            id: {namespace: 'field', type: 'IntegerField'},
                            name: {namespace: 'field', type: 'CharField'},
                            load: {namespace: 'callable'},
                        },
                    },
                },
            },
        })

        const childState = {
            id: {value: 2, errors: []},
            title: {value: 'Child Task', errors: []},
            parent_id: {value: 1, errors: []},
            parent: parentState,  // Eager: nested state directly
        }

        const proxy = new GlueModelProxy({
            http: http(),
            policy: childPolicy,
            state: childState,
            metadata: childMetadata,
        })
        proxy._loaded = true

        // parent should be a nested model proxy
        expect(proxy.parent).toBeInstanceOf(GlueModelProxy)
        // Nested proxy should be marked as loaded (has state)
        expect(proxy.parent._loaded).toBe(true)
        // Access fields without triggering load
        expect(proxy.parent.id).toBe(1)
        expect(proxy.parent.name).toBe('Parent Task')
        // parent_id should return raw FK value
        expect(proxy.parent_id).toBe(1)
    })

    test('lazy FK creates nested proxy that loads on access', async () => {
        registerProxyClass('model', GlueModelProxy)

        // Child model with lazy parent (no state, will load on access)
        // Note: When FK has a value, the nested policy REPLACES 'parent' string in attributes
        const childPolicy = createPolicy({
            name: 'child',
            namespace: 'model',
            attributes: [
                'id',
                'title',
                'parent_id',
                // Nested policy replaces 'parent' string (needed for lazy loading)
                createPolicy({
                    name: 'child.parent',
                    namespace: 'model',
                    attributes: ['id', 'name', 'load'],
                    identity: {target_pk: 1, pk_field_name: 'id'},
                }),
            ],
            identity: {target_pk: 2, pk_field_name: 'id'},
        })

        const childMetadata = createMetadata({
            attributes: {
                id: {namespace: 'field', type: 'IntegerField'},
                title: {namespace: 'field', type: 'CharField'},
                parent_id: {namespace: 'field', type: 'IntegerField'},
                parent: {
                    namespace: 'related_field',
                    lazy: true,
                    fk_attname: 'parent_id',
                    pk_field: 'id',
                    glue_namespace: 'model',
                    metadata: {
                        attributes: {
                            id: {namespace: 'field', type: 'IntegerField'},
                            name: {namespace: 'field', type: 'CharField'},
                            load: {namespace: 'callable'},
                        },
                    },
                },
            },
        })

        const childState = {
            id: {value: 2, errors: []},
            title: {value: 'Child Task', errors: []},
            parent_id: {value: 1, errors: []},
            parent: {},  // Lazy: empty state
        }

        // Mock fetch for load call
        let loadCalled = false
        global.fetch = async () => {
            loadCalled = true
            return new Response(JSON.stringify({
                state: {
                    id: {value: 1, errors: []},
                    name: {value: 'Loaded Parent', errors: []},
                },
            }), {status: 200, headers: {'Content-Type': 'application/json'}})
        }

        const proxy = new GlueModelProxy({
            http: http(),
            policy: childPolicy,
            state: childState,
            metadata: childMetadata,
        })
        proxy._loaded = true

        // parent should be a nested proxy
        expect(proxy.parent).toBeInstanceOf(GlueModelProxy)
        // Nested proxy should NOT be marked as loaded (empty state)
        expect(proxy.parent._loaded).toBe(false)
        // parent_id should still be available
        expect(proxy.parent_id).toBe(1)

        // Accessing a field should trigger load
        const _name = proxy.parent.name
        expect(loadCalled).toBe(true)
    })

    test('null FK returns null for nested proxy', () => {
        registerProxyClass('model', GlueModelProxy)

        // Child with no parent (null FK)
        // Note: When FK is null, there's no nested policy - only the 'parent' string
        const childPolicy = createPolicy({
            name: 'child',
            namespace: 'model',
            attributes: ['id', 'title', 'parent_id', 'parent'],
            identity: {target_pk: 2, pk_field_name: 'id'},
        })

        const childMetadata = createMetadata({
            attributes: {
                id: {namespace: 'field', type: 'IntegerField'},
                title: {namespace: 'field', type: 'CharField'},
                parent_id: {namespace: 'field', type: 'IntegerField'},
                parent: {
                    namespace: 'related_field',
                    lazy: true,
                    fk_attname: 'parent_id',
                    pk_field: 'id',
                },
            },
        })

        const childState = {
            id: {value: 2, errors: []},
            title: {value: 'Child Task', errors: []},
            parent_id: {value: null, errors: []},
            // No parent state since FK is null
        }

        const proxy = new GlueModelProxy({
            http: http(),
            policy: childPolicy,
            state: childState,
            metadata: childMetadata,
        })
        proxy._loaded = true

        // No nested policy, so parent should be null
        expect(proxy.parent).toBe(null)
        // parent_id should be null
        expect(proxy.parent_id).toBe(null)
    })
})
