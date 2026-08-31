import {describe, expect, test} from "bun:test"
import GlueConfig from "../src/config"
import GlueClient from "../src/client"
import GlueHttp from "../src/http"
import {RelationFieldGlue} from "../src/proxies/fields"
import BaseGlueProxy from "../src/proxies/base"
import GlueSequenceProxy from "../src/proxies/sequence"
import GlueFormProxy from "../src/proxies/form"
import GlueFormSetProxy from "../src/proxies/formset"
import GlueModelProxy from "../src/proxies/model"
import GlueQuerySetProxy from "../src/proxies/queryset"
import {registerProxyClass} from "../src/proxies/registry"
import {createPolicy, createPolicyToken, createMetadata, createState, mockOperationFetch} from "./testUtils"

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

function queryPolicyToken(name = 'gorillas') {
    return createPolicyToken({
        name,
        namespace: 'querySet',
        attributes: ['get', 'query_with_params'],
    })
}

function modelRow(name, id, values = {}) {
    return {
        is_glue_manifest: true,
        policy_token: createPolicyToken({
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
        state: {},
        metadata: queryMetadata(),
    })
}

describe('Glue proxies', () => {
    test('formsets send form_list state for callable attributes', async () => {
        const calls = mockOperationFetch({result: {success: true}})
        const formPolicy = createPolicy({
            name: 'contacts.form_list.0',
            namespace: 'form',
            attributes: ['name'],
        })
        const client = new GlueClient({
            manifest_list: [{
                is_glue_manifest: true,
                policy_token: createPolicyToken({
                    name: 'contacts',
                    namespace: 'formSet',
                    attributes: [formPolicy, 'save'],
                }),
                state: {'form_list.0': {name: {value: 'Ada'}}},
                metadata: {
                    attributes: {
                        'form_list.0': {
                            namespace: 'glue',
                            metadata: {attributes: {name: {namespace: 'field'}}},
                        },
                        save: {namespace: 'callable', takes_client_state: true},
                    },
                },
            }],
        })

        const formset = client.formSet.contacts
        await formset.save()

        expect(formset).toBeInstanceOf(GlueFormSetProxy)
        expect(JSON.parse(calls[0].options.body.get('state'))).toEqual({
            form_list: [{name: {value: 'Ada'}}],
        })
    })

    test('collections expose grouped item proxies by ref', () => {
        const client = new GlueClient({
            manifest_list: [
                {
                    is_glue_manifest: true,
                    policy_token: createPolicyToken({
                        name: 'time_entry_days',
                        namespace: 'sequence',
                        identity: {},
                        attributes: [],
                    }),
                    state: {
                        items: [
                            {
                                policy_token: createPolicyToken({
                                    name: 'day_1',
                                    namespace: 'timeEntryDay',
                                    attributes: ['date'],
                                }),
                                state: {date: {value: '2026-08-10'}},
                                metadata: {attributes: {date: {namespace: 'readonly'}}},
                            },
                        ],
                    },
                },
            ],
        })

        const collection = client.sequence.time_entry_days

        expect(collection).toBeInstanceOf(GlueSequenceProxy)
        expect(collection.items).toHaveLength(1)
        expect(collection.at(0)).toBeInstanceOf(BaseGlueProxy)
        expect(collection.at(0)._name).toBe('day_1')
        expect([...collection][0]._policy.namespace).toBe('timeEntryDay')
    })

    test('collections reuse item proxies across repeated access', () => {
        const client = new GlueClient({
            manifest_list: [
                {
                    is_glue_manifest: true,
                    policy_token: createPolicyToken({
                        name: 'time_entry_days',
                        namespace: 'sequence',
                        identity: {},
                        attributes: [],
                    }),
                    state: {
                        items: [
                            {
                                policy_token: createPolicyToken({
                                    name: 'day_1',
                                    namespace: 'timeEntryDay',
                                    attributes: ['date'],
                                }),
                                state: {date: {value: '2026-08-10'}},
                                metadata: {attributes: {date: {namespace: 'readonly'}}},
                            },
                        ],
                    },
                },
            ],
        })

        const collection = client.sequence.time_entry_days
        const firstAccess = collection.items[0]
        const secondAccess = collection.items[0]

        expect(secondAccess).toBe(firstAccess)
        expect(collection.at(0)).toBe(firstAccess)
    })

    test('collections update cached item proxies when response data changes', () => {
        const collection = new GlueSequenceProxy({
            http: http(),
            policy: createPolicy({
                name: 'time_entry_days',
                namespace: 'sequence',
                identity: {},
                attributes: [],
            }),
            state: {
                items: [
                    {
                        policy_token: createPolicyToken({
                            name: 'day_1',
                            namespace: 'timeEntryDay',
                            attributes: ['date'],
                        }),
                        state: {date: {value: '2026-08-10'}},
                        metadata: {attributes: {date: {namespace: 'readonly'}}},
                    },
                ],
            },
        })

        const item = collection.items[0]
        collection._applyResponse({
            state: {
                items: [
                    {
                        policy_token: createPolicyToken({
                            name: 'day_1',
                            namespace: 'timeEntryDay',
                            attributes: ['date', 'label'],
                        }),
                        state: {date: {value: '2026-08-11'}},
                        metadata: {attributes: {date: {namespace: 'readonly'}}},
                    },
                ],
            },
        })

        const updatedItem = collection.items[0]

        expect(updatedItem).toBe(item)
        expect(updatedItem.date).toBe('2026-08-11')
        expect(updatedItem._policy.attributes).toEqual(['date', 'label'])
    })

    test('formsets refresh cached form policies from policy tokens', () => {
        const initialFormPolicy = createPolicy({
            name: 'contacts.form_list.0',
            namespace: 'form',
            attributes: ['name'],
        })
        const formset = new GlueFormSetProxy({
            http: http(),
            policy: createPolicy({
                name: 'contacts',
                namespace: 'formSet',
                attributes: [initialFormPolicy],
            }),
            state: {'form_list.0': {name: {value: 'Ada'}}},
            metadata: {attributes: {'form_list.0': {metadata: createMetadata({namespace: 'form'})}}},
        })
        const originalForm = formset.forms[0]

        formset._applyResponse({
            policy_token: createPolicyToken({
                name: 'contacts',
                namespace: 'formSet',
                attributes: [createPolicy({
                    name: 'contacts.form_list.0',
                    namespace: 'form',
                    attributes: ['name', 'email'],
                })],
            }),
            state: {'form_list.0': {name: {value: 'Ada'}, email: {value: 'ada@example.com'}}},
        })

        expect(formset.forms[0]).toBe(originalForm)
        expect(originalForm._policy.attributes).toEqual(['name', 'email'])
        expect(originalForm._state.email.value).toBe('ada@example.com')
    })

    test('eager collections mark item proxies as loaded', async () => {
        let fetchCalled = false
        global.fetch = async () => {
            fetchCalled = true
            return new Response(JSON.stringify({}), {status: 200, headers: {'Content-Type': 'application/json'}})
        }
        const collection = new GlueSequenceProxy({
            http: http(),
            policy: createPolicy({
                name: 'entries',
                namespace: 'sequence',
                identity: {},
                attributes: [],
            }),
            state: {
                items: [
                    {
                        policy_token: createPolicyToken({
                            name: 'entries.1',
                            namespace: 'model',
                            attributes: ['id', 'name', 'load'],
                            identity: {target_pk: 1, pk_field_name: 'id'},
                        }),
                        state: createState({instance_data: {id: 1, name: 'Koko'}}),
                        metadata: createMetadata({attributes: {load: {namespace: 'callable'}}}),
                    },
                ],
            },
            loadingStrategy: 'eager',
        })

        const item = collection.items[0]

        expect(item._loaded).toBe(true)
        expect(item.name).toBe('Koko')
        await new Promise(resolve => setTimeout(resolve, 0))
        expect(fetchCalled).toBe(false)
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

    test('glue object attributes refresh nested proxy policy after response updates', () => {
        registerProxyClass('sequence', GlueSequenceProxy)
        const object = new BaseGlueProxy({
            http: http(),
            policy: createPolicy({
                name: 'dashboard',
                namespace: 'timeEntryDashboard',
                attributes: [
                    createPolicy({
                        name: 'dashboard.day_collection',
                        namespace: 'sequence',
                        attributes: [],
                    }),
                ],
            }),
            state: {
                day_collection: {items: []},
            },
            metadata: {
                attributes: {
                    day_collection: {
                        namespace: 'glue',
                        glue_namespace: 'sequence',
                        metadata: {attributes: {}},
                    },
                },
            },
        })

        expect(object.day_collection.items).toHaveLength(0)

        object._applyResponse({
            policy_token: createPolicyToken({
                name: 'dashboard',
                namespace: 'timeEntryDashboard',
                attributes: [
                    createPolicy({
                        name: 'dashboard.day_collection',
                        namespace: 'sequence',
                        attributes: [],
                    }),
                ],
            }),
            state: {
                day_collection: {
                    items: [
                        {
                            policy_token: createPolicyToken({
                                name: 'day_1',
                                namespace: 'timeEntryDay',
                                attributes: ['date'],
                            }),
                            state: {date: {value: '2026-08-10'}},
                            metadata: {attributes: {date: {namespace: 'readonly'}}},
                        },
                    ],
                },
            },
            metadata: {
                attributes: {
                    day_collection: {
                        namespace: 'glue',
                        glue_namespace: 'sequence',
                        metadata: {attributes: {}},
                    },
                },
            },
        })

        expect(object.day_collection.items).toHaveLength(1)
        expect(object.day_collection.items[0].date).toBe('2026-08-10')
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

    test('field proxy value access triggers lazy loading via load_state', async () => {
        let loadStateCalled = false
        global.fetch = async (_url, options) => {
            loadStateCalled = options.body.get('attribute') === 'load_state'
            return new Response(JSON.stringify({
                result: {groups: {value: [1], errors: []}},
                state: {groups: {value: [1], errors: []}},
                policy_token: createPolicyToken({
                    name: 'group_form',
                    namespace: 'form',
                    attributes: ['groups', 'load_state'],
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
                        load_state: {namespace: 'callable'},
                    },
                },
            }), {status: 200, headers: {'Content-Type': 'application/json'}})
        }
        const form = new GlueFormProxy({
            http: http(),
            policy: createPolicy({
                name: 'group_form',
                namespace: 'form',
                attributes: ['groups', 'load_state'],
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
                    load_state: {namespace: 'callable'},
                },
            },
        })

        expect(form.$fields.groups.hasChoiceSelected(1)).toBe(false)
        expect(loadStateCalled).toBe(true)
        await new Promise(resolve => setTimeout(resolve, 0))

        expect(form.$fields.groups.hasChoiceSelected(1)).toBe(true)
    })

    test('failed lazy loading does not retry on repeated field reads', async () => {
        let requestCount = 0
        global.fetch = async () => {
            requestCount += 1
            return new Response(JSON.stringify({error: {message: 'Forbidden'}}), {
                status: 403,
                headers: {'Content-Type': 'application/json'},
            })
        }
        const form = new GlueFormProxy({
            http: http(),
            policy: createPolicy({
                name: 'group_form',
                namespace: 'form',
                attributes: ['groups', 'load_state'],
            }),
            state: {},
            metadata: createMetadata({
                namespace: 'form',
                fields: {groups: {type: 'ModelMultipleChoiceField'}},
                attributes: {load_state: {namespace: 'callable'}},
            }),
        })

        void form.groups
        void form.groups
        await form._loadPromise
        void form.groups

        expect(requestCount).toBe(1)
        expect(form._loadError?.status).toBe(403)

        await form.retryLoad()
        expect(requestCount).toBe(2)
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

        expect(object._policy.token).toBe(createPolicyToken())
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
            result: {results: [{value: 1, label: 'Grappling', obj: {pk: 1, __str__: 'Grappling'}}], has_next: false, seek_key: null},
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

    test('overrideChoices() survives incidental reads that would otherwise re-trigger ensureChoices()', async () => {
        RelationFieldGlue.loadingCache.clear()
        mockOperationFetch({
            result: {results: [{value: 1, label: 'Grappling', obj: {pk: 1, __str__: 'Grappling'}}], has_next: false, seek_key: null},
            state: createState({instance_data: {id: 1, skills: []}}),
            policy: createPolicy({attributes: ['id', 'skills', 'foreign_key_choices']}),
            metadata: createMetadata({
                fields: {
                    skills: {
                        type: 'ManyToManyField',
                        label: 'Skills',
                        choices: [],
                        choice_model_path: 'test_project.gorilla.models.Skill',
                        choices_cache_key: 'gorilla.skills.override',
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
                        choices_cache_key: 'gorilla.skills.override',
                    },
                },
                attributes: {foreign_key_choices: {namespace: 'callable'}},
            }),
        })
        object._loaded = true

        // Let the field's default (cache-backed) choices load first, same
        // as a widget's own template read would trigger.
        expect(object.$fields.skills.choices).toEqual([])
        await new Promise(resolve => setTimeout(resolve, 0))
        expect(object.$fields.skills.choices).toEqual([
            {value: 1, label: 'Grappling', obj: {pk: 1, __str__: 'Grappling'}},
        ])

        // A caller supplies its own choices (e.g. a dependent-choices
        // glue-callable workaround) -- this must stick even though
        // reading `.choices` again would otherwise call ensureChoices()
        // and reset it back to the shared cache's value.
        const overridden = [{value: 99, label: 'Manually supplied'}]
        object.$fields.skills.overrideChoices(overridden)

        expect(object.$fields.skills.choices).toEqual(overridden)
        // Reading again (as a template re-render would) must not clobber it.
        expect(object.$fields.skills.choices).toEqual(overridden)

        // Reverting restores the normal cache-backed behavior.
        object.$fields.skills.clearChoicesOverride()
        expect(object.$fields.skills.choices).toEqual([
            {value: 1, label: 'Grappling', obj: {pk: 1, __str__: 'Grappling'}},
        ])
    })

    // Reads the `kwargs` field off a mocked fetch call's FormData body --
    // sendAttributeRequest() posts kwargs as a JSON string field, not a
    // JSON request body, so a plain mockOperationFetch() (one fixed
    // response for every call) can't tell requests in a batched-loading
    // sequence apart. These tests need to.
    function kwargsFromCall(call) {
        return JSON.parse(call.options.body.get('kwargs'))
    }

    function buildRelationObject(overrides = {}) {
        const metadata = createMetadata({
            fields: {
                skills: {
                    type: 'ManyToManyField',
                    label: 'Skills',
                    choices: [],
                    choice_model_path: 'test_project.gorilla.models.Skill',
                    choices_cache_key: overrides.cacheKey,
                    choices_batch_size: 2,
                },
            },
            attributes: {foreign_key_choices: {namespace: 'callable'}},
        })
        const policy = createPolicy({attributes: ['id', 'skills', 'foreign_key_choices']})
        const state = createState({instance_data: {id: 1, skills: []}})
        const object = new GlueModelProxy({http: http(), policy, state, metadata})
        object._loaded = true
        return object
    }

    test('loadMoreChoices() fetches the next batch and merges it into the cache', async () => {
        RelationFieldGlue.loadingCache.clear()
        const calls = []
        global.fetch = async (url, options) => {
            calls.push({url, options})
            const kwargs = kwargsFromCall(calls[calls.length - 1])
            const body = kwargs.seek_key === '2'
                ? {results: [{value: 3, label: 'Wrestling', obj: {pk: 3, __str__: 'Wrestling'}}], has_next: false, seek_key: null}
                : {results: [
                    {value: 1, label: 'Grappling', obj: {pk: 1, __str__: 'Grappling'}},
                    {value: 2, label: 'Striking', obj: {pk: 2, __str__: 'Striking'}},
                ], has_next: true, seek_key: '2'}
            return new Response(JSON.stringify({
                result: body,
                state: createState({instance_data: {id: 1, skills: []}}),
                policy_token: createPolicyToken(),
                metadata: createMetadata(),
                messages: [],
            }), {status: 200, headers: {'Content-Type': 'application/json'}})
        }

        const object = buildRelationObject({cacheKey: 'gorilla.skills.batched'})
        const field = object.$fields.skills

        expect(field.choices).toEqual([])
        await new Promise(resolve => setTimeout(resolve, 0))

        expect(field.choices.map(c => c.value)).toEqual([1, 2])
        expect(field.hasMoreChoices).toBe(true)

        await field.loadMoreChoices()

        expect(field.choices.map(c => c.value)).toEqual([1, 2, 3])
        expect(field.hasMoreChoices).toBe(false)

        // A batch_size=2 field must ask the server for at most 2 rows per
        // call -- confirms the client actually sent choices_batch_size
        // through, not just that the (mocked) server happened to paginate.
        expect(kwargsFromCall(calls[0]).batch_size).toBe(2)
    })

    test('searchChoices() takes over choices from the server and loadMoreChoices() continues that search', async () => {
        RelationFieldGlue.loadingCache.clear()
        const calls = []
        global.fetch = async (url, options) => {
            calls.push({url, options})
            const kwargs = kwargsFromCall(calls[calls.length - 1])
            let body
            if (kwargs.search === 'strike' && kwargs.seek_key === '10') {
                body = {results: [{value: 11, label: 'Kickboxing', obj: {pk: 11, __str__: 'Kickboxing'}}], has_next: false, seek_key: null}
            } else if (kwargs.search === 'strike') {
                body = {results: [{value: 10, label: 'Striking', obj: {pk: 10, __str__: 'Striking'}}], has_next: true, seek_key: '10'}
            } else {
                body = {results: [{value: 1, label: 'Grappling', obj: {pk: 1, __str__: 'Grappling'}}], has_next: false, seek_key: null}
            }
            return new Response(JSON.stringify({
                result: body,
                state: createState({instance_data: {id: 1, skills: []}}),
                policy_token: createPolicyToken(),
                metadata: createMetadata(),
                messages: [],
            }), {status: 200, headers: {'Content-Type': 'application/json'}})
        }

        const object = buildRelationObject({cacheKey: 'gorilla.skills.search'})
        const field = object.$fields.skills

        // Default (unsearched) choices load first, same as any other field.
        expect(field.choices).toEqual([])
        await new Promise(resolve => setTimeout(resolve, 0))
        expect(field.choices.map(c => c.value)).toEqual([1])

        await field.searchChoices('strike', 'name')
        expect(field.choices.map(c => c.value)).toEqual([10])
        expect(field.hasMoreChoices).toBe(true)
        expect(kwargsFromCall(calls[calls.length - 1]).search_field).toBe('name')

        await field.loadMoreChoices()
        expect(field.choices.map(c => c.value)).toEqual([10, 11])
        expect(field.hasMoreChoices).toBe(false)

        // Clearing the search reverts to the untouched default cache --
        // the search results never polluted it.
        field.clearSearch()
        expect(field.choices.map(c => c.value)).toEqual([1])
    })

    test('querysets build model proxies from returned row manifests', async () => {
        const object = querySet()
        const rows = [modelRow('gorillas.1', 1), modelRow('gorillas.2', 2)]
        global.fetch = async () => new Response(JSON.stringify({
            result: {items: rows},
            state: {},
            policy: queryPolicy(),
            metadata: queryMetadata(),
        }), {status: 200, headers: {'Content-Type': 'application/json'}})

        const filtered = await object.filter({name__icontains: 'ko'}).all()

        expect(filtered.items).toHaveLength(2)
        expect(filtered.items[0]).toBeInstanceOf(GlueModelProxy)
        expect(filtered.items[0].name).toBe('gorillas.1')
    })

    test('eager querysets build model proxies from initial state', async () => {
        const rows = [modelRow('gorillas.1', 1), modelRow('gorillas.2', 2)]
        let fetchCalled = false
        global.fetch = async () => {
            fetchCalled = true
            return new Response('{}', {status: 200, headers: {'Content-Type': 'application/json'}})
        }
        const object = new GlueQuerySetProxy({
            http: http(),
            policy: createPolicy({
                name: 'gorillas',
                namespace: 'querySet',
                attributes: ['get', 'query_with_params'],
            }),
            state: {items: rows},
            metadata: queryMetadata(),
            loadingStrategy: 'eager',
        })

        const result = await object.all()

        expect(result).toBe(object)
        expect(fetchCalled).toBe(false)
        expect(object.items).toHaveLength(2)
        expect(object.items[0]).toBeInstanceOf(GlueModelProxy)
        expect(object.items[0].name).toBe('gorillas.1')
    })

    test('eager queryset filtered clones still query the backend', async () => {
        const rows = [modelRow('gorillas.1', 1)]
        let kwargs
        global.fetch = async (_url, options) => {
            kwargs = JSON.parse(options.body.get('kwargs'))
            return new Response(JSON.stringify({
                result: {items: [modelRow('gorillas.2', 2)]},
                state: {},
                policy: queryPolicy(),
                metadata: queryMetadata(),
            }), {status: 200, headers: {'Content-Type': 'application/json'}})
        }
        const object = new GlueQuerySetProxy({
            http: http(),
            policy: createPolicy({
                name: 'gorillas',
                namespace: 'querySet',
                attributes: ['get', 'query_with_params'],
            }),
            state: {items: rows},
            metadata: queryMetadata(),
            loadingStrategy: 'eager',
        })

        const filtered = await object.filter({name__icontains: 'ndume'}).all()

        expect(kwargs).toEqual({filter: {name__icontains: 'ndume'}})
        expect(filtered.items).toHaveLength(1)
        expect(filtered.items[0].name).toBe('gorillas.2')
    })

    test('querysets expose computed attributes on returned model proxies', async () => {
        const object = querySet()
        const rows = [{
            is_glue_manifest: true,
            policy_token: createPolicyToken({
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
            state: {},
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
        expect(item.$owner).toBe(object)
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
                state: {},
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
            loadingStrategy: 'eager',
        })

        // parent should be a nested model proxy
        expect(proxy.parent).toBeInstanceOf(GlueModelProxy)
        // Nested proxy inherits parent's loading strategy
        expect(proxy.parent._loadingStrategy).toBe('eager')
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

    test('field-level lazy metadata overrides an eager parent strategy', async () => {
        registerProxyClass('model', GlueModelProxy)

        // Child model is eager overall, but this one FK field explicitly
        // declares lazy: true -- the field's own metadata must win, not the
        // parent's strategy (a real bug: the nested proxy used to always
        // inherit the parent's strategy, so an eager-per-field attribute on
        // a lazy parent -- or vice versa, as here -- got built with the
        // wrong strategy and no state).
        const childPolicy = createPolicy({
            name: 'child',
            namespace: 'model',
            attributes: [
                'id',
                'title',
                'parent_id',
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
                    lazy: true,  // overrides the parent's own 'eager' strategy below
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
            parent: {},  // Lazy shape: no eager nested state provided
        }

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
            loadingStrategy: 'eager',  // the parent itself is eager
        })
        proxy._loaded = true

        // The field's own lazy: true must win over the parent's 'eager'.
        expect(proxy.parent._loadingStrategy).toBe('lazy')
        expect(proxy.parent._loaded).toBe(false)

        // Accessing a field on it should trigger a load, same as a genuinely
        // lazy proxy would -- if the parent's strategy had won instead, this
        // would wrongly be treated as already-loaded with no state.
        const _name = proxy.parent.name
        expect(loadCalled).toBe(true)
    })
})

describe('QuerySet seek pagination', () => {
    function batchResponse(rows, {seek_key = null, has_next = false, batch_size = null} = {}) {
        return new Response(JSON.stringify({
            result: {items: rows, seek_key, has_next, batch_size},
            state: {},
            policy: queryPolicy(),
            metadata: queryMetadata(),
        }), {status: 200, headers: {'Content-Type': 'application/json'}})
    }

    test('loaded results expose batch size and hasNext', async () => {
        const object = querySet()
        global.fetch = async () => batchResponse(
            [modelRow('gorillas.3', 3), modelRow('gorillas.4', 4)],
            {seek_key: 'abc', has_next: true, batch_size: 2},
        )

        await object.all()

        expect(object.items).toHaveLength(2)
        expect(object.batchSize).toBe(2)
        expect(object.hasNext).toBe(true)
    })

    test('unpaginated results have no seek_key and no next batch', async () => {
        const object = querySet()
        global.fetch = async () => batchResponse([modelRow('gorillas.1', 1)])

        await object.all()

        expect(object.items).toHaveLength(1)
        expect(object.batchSize).toBeNull()
        expect(object.hasNext).toBe(false)
    })

    test('filter, orderBy and slice each produce an independent query proxy', () => {
        const object = querySet()

        expect(object.filter({name: 'Koko'})._queryParams).toEqual({filter: {name: 'Koko'}})
        expect(object.orderBy('name')._queryParams).toEqual({order_by: 'name'})
        expect(object.slice(0, 5)._queryParams).toEqual({slice: {start: 0, stop: 5}})
    })

    test('query cache is keyed on canonical merged params', () => {
        const object = querySet()

        expect(object.filter({a: 1}).orderBy('n')).toBe(object.orderBy('n').filter({a: 1}))
        expect(object.filter({a: 1}).filter({a: 1})).toBe(object.filter({a: 1}))
    })

    test('query cache is bounded', () => {
        const object = querySet()
        const first = object.filter({a: 2})

        for (let number = 3; number < 70; number += 1) {
            object.filter({a: number})
        }

        expect(object._queryCache.size).toBe(64)
        expect(object.filter({a: 2})).not.toBe(first)
    })
})

describe('QuerySet infinite scroll and seeding', () => {
    function batchResponse(rows, {seek_key = null, has_next = false, batch_size = null} = {}) {
        return new Response(JSON.stringify({
            result: {items: rows, seek_key, has_next, batch_size},
            state: {},
            policy: queryPolicy(),
            metadata: queryMetadata(),
        }), {status: 200, headers: {'Content-Type': 'application/json'}})
    }

    test('loadMore appends the next batch into the same proxy', async () => {
        const object = querySet()
        const requests = []
        let call = 0
        global.fetch = async (_url, options) => {
            const kwargs = JSON.parse(options.body.get('kwargs'))
            requests.push(kwargs)
            call += 1
            return batchResponse(
                [modelRow(`gorillas.${call * 2 - 1}`, call * 2 - 1), modelRow(`gorillas.${call * 2}`, call * 2)],
                {seek_key: `seek-${call}`, has_next: call < 3, batch_size: 2},
            )
        }

        await object.all()
        expect(object.items).toHaveLength(2)
        expect(object.hasNext).toBe(true)

        const same = await object.loadMore()
        expect(same).toBe(object)
        expect(object.items.map(item => item.name)).toEqual(['gorillas.1', 'gorillas.2', 'gorillas.3', 'gorillas.4'])
        expect(object.hasNext).toBe(true)

        await object.loadMore()
        expect(object.items).toHaveLength(6)
        expect(object.hasNext).toBe(false)

        await object.loadMore()
        expect(requests.map(request => request.seek_key ?? null)).toEqual([null, 'seek-1', 'seek-2'])
    })

    test('loadMore on an unloaded proxy loads the first batch', async () => {
        const object = querySet()
        global.fetch = async () => batchResponse([modelRow('gorillas.1', 1)], {batch_size: 10})

        await object.loadMore()

        expect(object.items).toHaveLength(1)
        expect(object.loading).toBe(false)
    })

    test('loadMore does not double fetch while a request is in flight', async () => {
        const object = querySet()
        let fetches = 0
        global.fetch = async () => {
            fetches += 1
            await new Promise(resolve => setTimeout(resolve, 10))
            return batchResponse([modelRow('gorillas.1', 1)], {seek_key: 'next', has_next: true, batch_size: 1})
        }

        await object.all()
        const first = object.loadMore()
        const second = object.loadMore()
        await Promise.all([first, second])

        expect(fetches).toBe(2)
    })

    test('a chained query proxy starts unloaded, independent of its source', async () => {
        const object = querySet()
        global.fetch = async () => batchResponse(
            [modelRow('gorillas.1', 1), modelRow('gorillas.2', 2)],
            {seek_key: 'seek-1', has_next: true, batch_size: 2},
        )
        await object.all()

        const filtered = object.filter({name: 'Koko'})

        expect(filtered._loaded).toBe(false)
        expect(filtered).not.toBe(object)
    })
})

describe('QuerySet count', () => {
    test('count calls the count attribute with the current filter', async () => {
        const object = querySet()
        let kwargs
        global.fetch = async (_url, options) => {
            kwargs = JSON.parse(options.body.get('kwargs'))
            return new Response(JSON.stringify({
                result: 7,
                state: {},
                policy: queryPolicy(),
                metadata: queryMetadata(),
            }), {status: 200, headers: {'Content-Type': 'application/json'}})
        }

        const total = await object.filter({name__icontains: 'Ko'}).count()

        expect(total).toBe(7)
        expect(kwargs).toEqual({filter: {name__icontains: 'Ko'}})
    })
})

describe('QuerySet with_total', () => {
    function batchResponse(rows, {seek_key = null, has_next = false, batch_size = null, total} = {}) {
        const result = {items: rows, seek_key, has_next, batch_size}
        if (total !== undefined) {
            result.total = total
        }
        return new Response(JSON.stringify({
            result,
            state: {},
            policy: queryPolicy(),
            metadata: queryMetadata(),
        }), {status: 200, headers: {'Content-Type': 'application/json'}})
    }

    test('all() without withTotal never asks for a total', async () => {
        const object = querySet()
        let kwargs
        global.fetch = async (_url, options) => {
            kwargs = JSON.parse(options.body.get('kwargs'))
            return batchResponse([modelRow('gorillas.1', 1)], {batch_size: 10})
        }

        await object.all()

        expect(kwargs.with_total).toBeUndefined()
        expect(object.total).toBeNull()
    })

    test('all({withTotal: true}) requests and stores the total', async () => {
        const object = querySet()
        let kwargs
        global.fetch = async (_url, options) => {
            kwargs = JSON.parse(options.body.get('kwargs'))
            return batchResponse([modelRow('gorillas.1', 1)], {batch_size: 10, total: 42})
        }

        await object.all({withTotal: true})

        expect(kwargs.with_total).toBe(true)
        expect(object.total).toBe(42)
    })

    test('loadMore() does not clobber a total fetched by an earlier all()', async () => {
        const object = querySet()
        let call = 0
        global.fetch = async () => {
            call += 1
            return batchResponse(
                [modelRow(`gorillas.${call}`, call)],
                call === 1
                    ? {seek_key: 'seek-1', has_next: true, batch_size: 1, total: 42}
                    : {seek_key: null, has_next: false, batch_size: 1},
            )
        }

        await object.all({withTotal: true})
        expect(object.total).toBe(42)

        await object.loadMore()

        expect(object.total).toBe(42)
    })
})
