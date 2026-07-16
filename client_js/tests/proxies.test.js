import {describe, expect, test} from "bun:test"
import GlueConfig from "../src/config"
import GlueHttp from "../src/http"
import {RelationFieldGlue} from "../src/proxies/fields"
import GlueModelProxy from "../src/proxies/model"
import GlueQuerySetProxy from "../src/proxies/queryset"
import {createPolicy, createMetadata, createState, mockOperationFetch} from "./testUtils"

describe('Glue proxies', () => {
    test('Django field proxies expose metadata fields and parse date values as Date instances', () => {
        const object = new GlueModelProxy({
            http: new GlueHttp(new GlueConfig()),
            name: 'gorilla',
            policy: createPolicy(),
            state: createState(),
            metadata: createMetadata(),
        })

        expect(String(object.name)).toBe('Koko')
        expect(object.name.value).toBe('Koko')
        expect(object.birthday.value).toBeInstanceOf(Date)
        expect(object.$fields.birthday.value).toBe(object.birthday.value)
        expect(object.$fields.pk).toBeUndefined()
        expect(object.$pk).toBe(1)
        expect(object.name.label).toBe('Name')

        object.name = 'Ndume'
        expect(object.$state.instance_data.name).toBe('Ndume')
        expect(object.name.value).toBe('Ndume')
    })

    test('attribute requests apply refreshed policy, state, and metadata from the server', async () => {
        mockOperationFetch()
        const object = new GlueModelProxy({
            http: new GlueHttp(new GlueConfig()),
            name: 'gorilla',
            policy: createPolicy(),
            state: createState(),
            metadata: createMetadata(),
        })

        await object.save()

        expect(object.$policy.original_signature).toBe('next-signature')
        expect(String(object.name)).toBe('Michael')
        expect(object.birthday.value).toBeInstanceOf(Date)
    })

    test('dotted callable attributes are exposed as nested objects', async () => {
        let capturedAttribute = null
        global.fetch = async (_url, options) => {
            capturedAttribute = options.body.get('attribute')
            return new Response(JSON.stringify({
                result: {ok: true},
                state: createState(),
                policy: createPolicy({
                    attributes: ['id', 'name', 'services.increment_age'],
                    original_signature: 'next-signature',
                }),
                metadata: createMetadata({
                    attributes: {
                        'services.increment_age': {namespace: 'callable'},
                    },
                }),
                messages: [],
            }), {
                status: 200,
                headers: {'Content-Type': 'application/json'},
            })
        }
        const object = new GlueModelProxy({
            http: new GlueHttp(new GlueConfig()),
            name: 'gorilla',
            policy: createPolicy({attributes: ['id', 'name', 'services.increment_age']}),
            state: createState(),
            metadata: createMetadata({
                attributes: {
                    'services.increment_age': {namespace: 'callable'},
                },
            }),
        })

        const result = await object.services.increment_age()

        expect(result).toEqual({ok: true})
        expect(capturedAttribute).toBe('services.increment_age')
    })

    test('field proxies keep identity and read refreshed state after attribute responses', async () => {
        global.fetch = async () => {
            return new Response(JSON.stringify({
                result: null,
                state: createState({instance_data: {id: 1, name: 'Koko', age: 19}}),
                policy: createPolicy({
                    attributes: ['id', 'name', 'age', 'services.increment_age'],
                    original_signature: 'next-signature',
                }),
                metadata: createMetadata({
                    fields: {
                        id: {type: 'AutoField', label: 'ID'},
                        name: {type: 'CharField', label: 'Name'},
                        age: {type: 'IntegerField', label: 'Age'},
                    },
                    attributes: {
                        'services.increment_age': {namespace: 'callable'},
                    },
                }),
                messages: [],
            }), {
                status: 200,
                headers: {'Content-Type': 'application/json'},
            })
        }
        const object = new GlueModelProxy({
            http: new GlueHttp(new GlueConfig()),
            name: 'gorilla',
            policy: createPolicy({attributes: ['id', 'name', 'age', 'services.increment_age']}),
            state: createState({instance_data: {id: 1, name: 'Koko', age: 18}}),
            metadata: createMetadata({
                fields: {
                    id: {type: 'AutoField', label: 'ID'},
                    name: {type: 'CharField', label: 'Name'},
                    age: {type: 'IntegerField', label: 'Age'},
                },
                attributes: {
                    'services.increment_age': {namespace: 'callable'},
                },
            }),
        })
        const ageField = object.$fields.age

        await object.services.increment_age()

        expect(object.$fields.age).toBe(ageField)
        expect(ageField.value).toBe(19)
        expect(Number(object.age)).toBe(19)
    })

    test('nested callables update through the current receiver instead of a captured raw object', async () => {
        global.fetch = async () => {
            return new Response(JSON.stringify({
                result: null,
                state: createState({instance_data: {id: 1, name: 'Koko', age: 19}}),
                policy: createPolicy({
                    attributes: ['id', 'name', 'age', 'services.increment_age'],
                    original_signature: 'next-signature',
                }),
                metadata: createMetadata({
                    fields: {
                        id: {type: 'AutoField', label: 'ID'},
                        name: {type: 'CharField', label: 'Name'},
                        age: {type: 'IntegerField', label: 'Age'},
                    },
                    attributes: {
                        'services.increment_age': {namespace: 'callable'},
                    },
                }),
                messages: [],
            }), {
                status: 200,
                headers: {'Content-Type': 'application/json'},
            })
        }
        const object = new GlueModelProxy({
            http: new GlueHttp(new GlueConfig()),
            name: 'gorilla',
            policy: createPolicy({attributes: ['id', 'name', 'age', 'services.increment_age']}),
            state: createState({instance_data: {id: 1, name: 'Koko', age: 18}}),
            metadata: createMetadata({
                fields: {
                    id: {type: 'AutoField', label: 'ID'},
                    name: {type: 'CharField', label: 'Name'},
                    age: {type: 'IntegerField', label: 'Age'},
                },
                attributes: {
                    'services.increment_age': {namespace: 'callable'},
                },
            }),
        })
        const receiver = new Proxy(object, {
            get(target, prop, receiver) {
                return Reflect.get(target, prop, receiver)
            },
            set(target, prop, value, receiver) {
                return Reflect.set(target, prop, value, receiver)
            },
        })

        await receiver.services.increment_age()

        expect(receiver.$state.instance_data.age).toBe(19)
        expect(receiver.$fields.age.value).toBe(19)
    })

    test('service calls update a DOM input bound to field value', async () => {
        global.fetch = async () => {
            return new Response(JSON.stringify({
                result: null,
                state: createState({instance_data: {id: 1, name: 'Koko', age: 19}}),
                policy: createPolicy({
                    attributes: ['id', 'name', 'age', 'services.increment_age'],
                    original_signature: 'next-signature',
                }),
                metadata: createMetadata({
                    fields: {
                        id: {type: 'AutoField', label: 'ID'},
                        name: {type: 'CharField', label: 'Name'},
                        age: {type: 'IntegerField', label: 'Age'},
                    },
                    attributes: {
                        'services.increment_age': {namespace: 'callable'},
                    },
                }),
                messages: [],
            }), {
                status: 200,
                headers: {'Content-Type': 'application/json'},
            })
        }
        const object = new GlueModelProxy({
            http: new GlueHttp(new GlueConfig()),
            name: 'gorilla',
            policy: createPolicy({attributes: ['id', 'name', 'age', 'services.increment_age']}),
            state: createState({instance_data: {id: 1, name: 'Koko', age: 18}}),
            metadata: createMetadata({
                fields: {
                    id: {type: 'AutoField', label: 'ID'},
                    name: {type: 'CharField', label: 'Name'},
                    age: {type: 'IntegerField', label: 'Age'},
                },
                attributes: {
                    'services.increment_age': {namespace: 'callable'},
                },
            }),
        })
        const input = document.createElement('input')
        input.type = 'number'
        document.body.appendChild(input)

        const render = () => {
            input.value = String(object.$fields.age.value)
        }
        object.$fields.age = new Proxy(object.$fields.age, {
            set(target, property, value, receiver) {
                const result = Reflect.set(target, property, value, receiver)
                if (property === 'value') {
                    render()
                }
                return result
            },
        })
        render()

        await object.services.increment_age()

        expect(input.value).toBe('19')
        input.remove()
    })

    test('django relation fields expose stable lazy-loading choices', async () => {
        const metadata = createMetadata({
            fields: {
                id: {type: 'AutoField', label: 'ID'},
                skills: {
                    type: 'ManyToManyField',
                    label: 'Skills',
                    choices: [],
                    pk_field: 'id',
                    choice_model_path: 'test_project.gorilla.models.Skill',
                    choices_cache_key: 'gorilla.skills.gorilla.skill',
                },
            },
            attributes: {
                foreign_key_choices: {namespace: 'callable'},
            },
        })
        mockOperationFetch({
            result: [{pk: 1, __str__: 'Grappling'}],
            state: createState({instance_data: {id: 1, skills: []}}),
            policy: createPolicy({
                attributes: ['id', 'skills', 'foreign_key_choices'],
                original_signature: 'next-signature',
            }),
            metadata,
        })
        const object = new GlueModelProxy({
            http: new GlueHttp(new GlueConfig()),
            name: 'gorilla',
            policy: createPolicy({attributes: ['id', 'skills', 'foreign_key_choices']}),
            state: createState({instance_data: {id: 1, skills: []}}),
            metadata,
        })

        const choices = object.$fields.skills.choices
        expect(choices).toEqual([])
        expect(object.skills.map(skill => skill.pk)).toEqual([])

        await new Promise(resolve => setTimeout(resolve, 0))

        expect(object.skills.choices).toEqual([{pk: 1, __str__: 'Grappling'}])

        object.skills = [{pk: 1, __str__: 'Grappling'}]
        expect(object.skills.map(skill => skill.__str__)).toEqual(['Grappling'])
        expect([...object.skills]).toEqual([{pk: 1, __str__: 'Grappling'}])
        expect(object.skills.selectedPks).toEqual([1])
        expect(object.skills.selectedChoices).toEqual([{pk: 1, __str__: 'Grappling'}])
        expect(object.skills.has(1)).toBe(true)
    })

    test('django choice and relation fields expose selected choices', async () => {
        const object = new GlueModelProxy({
            http: new GlueHttp(new GlueConfig()),
            name: 'fight',
            policy: createPolicy({attributes: ['id', 'status', 'red_corner', 'foreign_key_choices']}),
            state: createState({instance_data: {id: 1, status: 'sch', red_corner: 2}}),
            metadata: createMetadata({
                fields: {
                    id: {type: 'AutoField', label: 'ID'},
                    status: {
                        type: 'CharField',
                        label: 'Status',
                        choices: [['sch', 'Scheduled'], ['pst', 'Postponed']],
                    },
                    red_corner: {
                        type: 'ForeignKey',
                        label: 'Red corner',
                        choices: [],
                        pk_field: 'id',
                        choice_model_path: 'test_project.gorilla.models.Gorilla',
                        choices_cache_key: 'fight.red_corner.gorilla',
                    },
                },
                attributes: {
                    foreign_key_choices: {namespace: 'callable'},
                },
            }),
        })
        object.red_corner.choices = [
            {pk: 1, __str__: 'Koko', rank_points: 100},
            {pk: 2, __str__: 'Michael', rank_points: 200},
        ]

        expect(object.status.selectedChoice).toEqual(['sch', 'Scheduled'])
        expect(object.status.selectedLabel).toBe('Scheduled')
        expect(object.red_corner.pk).toBe(2)
        expect(object.red_corner.selectedChoice).toEqual({pk: 2, __str__: 'Michael', rank_points: 200})
        expect(object.red_corner.selectedLabel).toBe('Michael')
    })

    test('relation choices loaded through direct field interface update bound DOM', async () => {
        RelationFieldGlue.choicesCache?.clear?.()
        global.fetch = async () => {
            return new Response(JSON.stringify({
                result: [{pk: 1, __str__: 'Grappling'}, {pk: 2, __str__: 'Climbing'}],
                state: createState({instance_data: {id: 1, skills: []}}),
                policy: createPolicy({
                    attributes: ['id', 'skills', 'foreign_key_choices'],
                    original_signature: 'next-signature',
                }),
                metadata: createMetadata({
                    fields: {
                        id: {type: 'AutoField', label: 'ID'},
                        skills: {
                            type: 'ManyToManyField',
                            label: 'Skills',
                            choices: [],
                            pk_field: 'id',
                            choice_model_path: 'test_project.gorilla.models.Skill',
                            choices_cache_key: 'gorilla.skills.gorilla.skill.dom',
                        },
                    },
                    attributes: {
                        foreign_key_choices: {namespace: 'callable'},
                    },
                }),
                messages: [],
            }), {
                status: 200,
                headers: {'Content-Type': 'application/json'},
            })
        }
        const object = new GlueModelProxy({
            http: new GlueHttp(new GlueConfig()),
            name: 'gorilla',
            policy: createPolicy({attributes: ['id', 'skills', 'foreign_key_choices']}),
            state: createState({instance_data: {id: 1, skills: []}}),
            metadata: createMetadata({
                fields: {
                    id: {type: 'AutoField', label: 'ID'},
                    skills: {
                        type: 'ManyToManyField',
                        label: 'Skills',
                        choices: [],
                        pk_field: 'id',
                        choice_model_path: 'test_project.gorilla.models.Skill',
                        choices_cache_key: 'gorilla.skills.gorilla.skill.dom',
                    },
                },
                attributes: {
                    foreign_key_choices: {namespace: 'callable'},
                },
            }),
        })
        const container = document.createElement('div')
        document.body.appendChild(container)

        const render = () => {
            container.innerHTML = object.skills.choices
                .map(choice => `<label><input type="checkbox" value="${choice.pk}">${choice.__str__}</label>`)
                .join('')
        }
        object.$fields.skills = new Proxy(object.$fields.skills, {
            set(target, property, value, receiver) {
                const result = Reflect.set(target, property, value, receiver)
                if (property === 'choices') {
                    render()
                }
                return result
            },
        })

        render()
        expect(container.querySelectorAll('input').length).toBe(0)

        await new Promise(resolve => setTimeout(resolve, 0))

        expect(container.querySelectorAll('input').length).toBe(2)
        expect(Array.from(container.querySelectorAll('label')).map(label => label.textContent)).toEqual([
            'Grappling',
            'Climbing',
        ])
        container.remove()
    })

    test('relation choices loaded once update multiple fields sharing the same cache', async () => {
        RelationFieldGlue.choicesCache?.clear?.()
        let requestCount = 0
        global.fetch = async () => {
            requestCount += 1
            return new Response(JSON.stringify({
                result: [{pk: 1, __str__: 'Grappling'}, {pk: 2, __str__: 'Climbing'}],
                state: createState({instance_data: {id: 1, skills: []}}),
                policy: createPolicy({
                    attributes: ['id', 'skills', 'foreign_key_choices'],
                    original_signature: 'next-signature',
                }),
                metadata: createMetadata({
                    fields: {
                        id: {type: 'AutoField', label: 'ID'},
                        skills: {
                            type: 'ManyToManyField',
                            label: 'Skills',
                            choices: [],
                            pk_field: 'id',
                            choice_model_path: 'test_project.gorilla.models.Skill',
                            choices_cache_key: 'gorilla.skills.gorilla.skill.shared',
                        },
                    },
                    attributes: {
                        foreign_key_choices: {namespace: 'callable'},
                    },
                }),
                messages: [],
            }), {
                status: 200,
                headers: {'Content-Type': 'application/json'},
            })
        }
        const metadata = createMetadata({
            fields: {
                id: {type: 'AutoField', label: 'ID'},
                skills: {
                    type: 'ManyToManyField',
                    label: 'Skills',
                    choices: [],
                    pk_field: 'id',
                    choice_model_path: 'test_project.gorilla.models.Skill',
                    choices_cache_key: 'gorilla.skills.gorilla.skill.shared',
                },
            },
            attributes: {
                foreign_key_choices: {namespace: 'callable'},
            },
        })
        const first = new GlueModelProxy({
            http: new GlueHttp(new GlueConfig()),
            name: 'gorillas.1',
            policy: createPolicy({name: 'gorillas.1', attributes: ['id', 'skills', 'foreign_key_choices']}),
            state: createState({instance_data: {id: 1, skills: [{pk: 1, __str__: 'Grappling'}]}}),
            metadata,
        })
        const second = new GlueModelProxy({
            http: new GlueHttp(new GlueConfig()),
            name: 'gorillas.2',
            policy: createPolicy({name: 'gorillas.2', attributes: ['id', 'skills', 'foreign_key_choices']}),
            state: createState({instance_data: {id: 2, skills: []}}),
            metadata,
        })
        const container = document.createElement('div')
        document.body.appendChild(container)

        container.innerHTML = '<section data-card="first"></section><section data-card="second"></section>'
        const renders = new Map([
            [first, () => {
                container.querySelector('[data-card="first"]').textContent = first.skills.choices
                    .map(choice => choice.__str__)
                    .join(',')
            }],
            [second, () => {
                container.querySelector('[data-card="second"]').textContent = second.skills.choices
                    .map(choice => choice.__str__)
                    .join(',')
            }],
        ])
        ;[first, second].forEach(object => {
            object.$fields.skills = new Proxy(object.$fields.skills, {
                set(target, property, value, receiver) {
                    const previous = target[property]
                    const result = Reflect.set(target, property, value, receiver)
                    if (property === 'choices' && previous !== value) {
                        renders.get(object)()
                    }
                    return result
                },
            })
        })

        renders.get(first)()
        renders.get(second)()
        expect(Array.from(container.querySelectorAll('section')).map(section => section.textContent)).toEqual(['', ''])
        const firstInitialChoices = first.skills.choices
        const secondInitialChoices = second.skills.choices

        await new Promise(resolve => setTimeout(resolve, 0))

        expect(requestCount).toBe(1)
        expect(first.skills.choices).not.toBe(firstInitialChoices)
        expect(second.skills.choices).not.toBe(secondInitialChoices)
        expect(Array.from(container.querySelectorAll('section')).map(section => section.textContent)).toEqual([
            'Grappling,Climbing',
            'Grappling,Climbing',
        ])
        container.remove()
    })

    test('django relation field choices remain stable after save responses', async () => {
        const metadata = createMetadata({
            fields: {
                id: {type: 'AutoField', label: 'ID'},
                skills: {
                    type: 'ManyToManyField',
                    label: 'Skills',
                    pk_field: 'id',
                    choice_model_path: 'test_project.gorilla.models.Skill',
                    choices_cache_key: 'gorilla.skills.gorilla.skill',
                },
            },
            attributes: {
                save: {namespace: 'callable'},
                foreign_key_choices: {namespace: 'callable'},
            },
        })
        mockOperationFetch({
            state: createState({instance_data: {id: 1, skills: [{pk: 1, __str__: 'Grappling'}]}}),
            policy: createPolicy({
                attributes: ['id', 'skills', 'save', 'foreign_key_choices'],
                original_signature: 'next-signature',
            }),
            metadata,
        })
        const object = new GlueModelProxy({
            http: new GlueHttp(new GlueConfig()),
            name: 'gorilla',
            policy: createPolicy({attributes: ['id', 'skills', 'save', 'foreign_key_choices']}),
            state: createState({instance_data: {id: 1, skills: []}}),
            metadata,
        })

        await object.save()

        expect(Array.isArray(object.$fields.skills.choices)).toBe(true)
        expect(() => object.$fields.skills.choices.filter(choice => choice.pk === 1)).not.toThrow()
        expect(object.skills.map(skill => skill.__str__)).toEqual(['Grappling'])
    })

    test('queryset proxies query through query_with_params and expose returned rows', async () => {
        mockOperationFetch({
            result: {items: [{id: 1, name: 'Koko'}, {id: 2, name: 'Michael'}]},
            state: {items: [{id: 1, name: 'Koko'}, {id: 2, name: 'Michael'}]},
            policy: createPolicy({
                namespace: 'querySet',
                attributes: ['query_with_params'],
                original_signature: 'next-signature',
            }),
            metadata: createMetadata({
                namespace: 'querySet',
                attributes: {query_with_params: {namespace: 'callable'}},
            }),
        })
        const object = new GlueQuerySetProxy({
            http: new GlueHttp(new GlueConfig()),
            name: 'gorillas',
            policy: createPolicy({
                name: 'gorillas',
                namespace: 'querySet',
                attributes: ['query_with_params'],
            }),
            state: {items: []},
            metadata: createMetadata({
                namespace: 'querySet',
                attributes: {query_with_params: {namespace: 'callable'}},
            }),
        })

        const filtered = await object.filter({name__icontains: 'ko'}).all()

        expect(object.items.length).toBe(0)
        expect(object.$policy.original_signature).toBe('signature')
        expect(filtered.length).toBe(2)
        expect(String(filtered[0].name)).toBe('Koko')
        expect([...filtered].map(row => String(row.name))).toEqual(['Koko', 'Michael'])
    })

    test('queryset filters return independent proxy copies for nested scopes', async () => {
        global.fetch = async (_url, options) => {
            const kwargs = JSON.parse(options.body.get('kwargs'))
            const parentId = kwargs.filter?.parent_id
            const name = parentId === 1 ? 'Alpha Child' : 'Beta Child'
            return new Response(JSON.stringify({
                result: {items: [{id: parentId, name}]},
                state: {items: [{id: parentId, name}]},
                policy: createPolicy({
                    namespace: 'querySet',
                    attributes: ['query_with_params'],
                    original_signature: `signature-${parentId}`,
                }),
                metadata: createMetadata({
                    namespace: 'querySet',
                    attributes: {query_with_params: {namespace: 'callable'}},
                }),
                messages: [],
            }), {
                status: 200,
                headers: {'Content-Type': 'application/json'},
            })
        }
        const source = new GlueQuerySetProxy({
            http: new GlueHttp(new GlueConfig()),
            name: 'subtasks',
            policy: createPolicy({
                name: 'subtasks',
                namespace: 'querySet',
                attributes: ['query_with_params'],
            }),
            state: {items: []},
            metadata: createMetadata({
                namespace: 'querySet',
                attributes: {query_with_params: {namespace: 'callable'}},
            }),
        })

        const alpha = await source.filter({parent_id: 1}).all()
        const beta = await source.fetchWithParams({filter: {parent_id: 2}})

        expect(source.items).toEqual([])
        expect(alpha).not.toBe(beta)
        expect(String(alpha[0].name)).toBe('Alpha Child')
        expect(String(beta[0].name)).toBe('Beta Child')
    })

    test('queryWithParams returns stable derived arrays for Alpine render expressions', async () => {
        global.fetch = async (_url, options) => {
            const kwargs = JSON.parse(options.body.get('kwargs'))
            const parentId = kwargs.filter?.parent_id
            const name = parentId === 1 ? 'Alpha Child' : 'Beta Child'
            return new Response(JSON.stringify({
                result: {items: [{id: parentId, name}]},
                state: {items: [{id: parentId, name}]},
                policy: createPolicy({
                    namespace: 'querySet',
                    attributes: ['query_with_params'],
                    original_signature: `signature-${parentId}`,
                }),
                metadata: createMetadata({
                    namespace: 'querySet',
                    attributes: {query_with_params: {namespace: 'callable'}},
                }),
                messages: [],
            }), {
                status: 200,
                headers: {'Content-Type': 'application/json'},
            })
        }
        const source = new GlueQuerySetProxy({
            http: new GlueHttp(new GlueConfig()),
            name: 'subtasks',
            policy: createPolicy({
                name: 'subtasks',
                namespace: 'querySet',
                attributes: ['query_with_params'],
            }),
            state: {items: []},
            metadata: createMetadata({
                namespace: 'querySet',
                attributes: {query_with_params: {namespace: 'callable'}},
            }),
        })

        const alpha = source.queryWithParams({filter: {parent_id: 1}})
        const beta = source.queryWithParams({filter: {parent_id: 2}})

        expect(alpha).toEqual([])
        expect(beta).toEqual([])

        await new Promise(resolve => setTimeout(resolve, 0))

        expect(source.items).toEqual([])
        expect(String(source.queryWithParams({filter: {parent_id: 1}})[0].name)).toBe('Alpha Child')
        expect(String(source.queryWithParams({filter: {parent_id: 2}})[0].name)).toBe('Beta Child')
        expect(source.queryWithParams({filter: {parent_id: 1}})).not.toBe(source.queryWithParams({filter: {parent_id: 2}}))
    })

    test('queryWithParams keeps the current result cache while new params load', async () => {
        global.fetch = async (_url, options) => {
            const kwargs = JSON.parse(options.body.get('kwargs'))
            const search = kwargs.filter?.name__icontains
            const name = search === 'mi' ? 'Michael' : 'Koko'
            return new Response(JSON.stringify({
                result: {items: [{id: 1, name}]},
                state: {items: [{id: 1, name}]},
                policy: createPolicy({
                    namespace: 'querySet',
                    attributes: ['query_with_params'],
                    original_signature: `signature-${search}`,
                }),
                metadata: createMetadata({
                    namespace: 'querySet',
                    attributes: {query_with_params: {namespace: 'callable'}},
                }),
                messages: [],
            }), {
                status: 200,
                headers: {'Content-Type': 'application/json'},
            })
        }
        const source = new GlueQuerySetProxy({
            http: new GlueHttp(new GlueConfig()),
            name: 'gorillas',
            policy: createPolicy({
                name: 'gorillas',
                namespace: 'querySet',
                attributes: ['query_with_params'],
            }),
            state: {items: []},
            metadata: createMetadata({
                namespace: 'querySet',
                attributes: {query_with_params: {namespace: 'callable'}},
            }),
        })

        source.queryWithParams({filter: {name__icontains: 'ko'}})
        await new Promise(resolve => setTimeout(resolve, 0))

        const visibleRows = source.queryWithParams({filter: {name__icontains: 'mi'}})

        expect(String(visibleRows[0].name)).toBe('Koko')

        await new Promise(resolve => setTimeout(resolve, 0))

        expect(String(source.queryWithParams({filter: {name__icontains: 'mi'}})[0].name)).toBe('Michael')
    })

    test('queryset chain methods accumulate params and all executes one request', async () => {
        const calls = []
        global.fetch = async (_url, options) => {
            calls.push(JSON.parse(options.body.get('kwargs')))
            return new Response(JSON.stringify({
                result: {items: [{id: 1, name: 'Koko'}]},
                state: {items: [{id: 1, name: 'Koko'}]},
                policy: createPolicy({
                    namespace: 'querySet',
                    attributes: ['query_with_params'],
                    original_signature: 'next-signature',
                }),
                metadata: createMetadata({
                    namespace: 'querySet',
                    attributes: {query_with_params: {namespace: 'callable'}},
                }),
                messages: [],
            }), {
                status: 200,
                headers: {'Content-Type': 'application/json'},
            })
        }
        const source = new GlueQuerySetProxy({
            http: new GlueHttp(new GlueConfig()),
            name: 'gorillas',
            policy: createPolicy({
                name: 'gorillas',
                namespacespace: 'querySet',
                attributes: ['query_with_params'],
            }),
            state: {items: []},
            metadata: createMetadata({
                namespace: 'querySet',
                attributes: {query_with_params: {namespace: 'callable'}},
            }),
        })

        const queried = await source
            .filter({name__icontains: 'ko'})
            .orderBy('name')
            .slice(0, 100)
            .all()

        expect(calls).toEqual([{
            filter: {name__icontains: 'ko'},
            order_by: 'name',
            slice: {start: 0, stop: 100},
        }])
        expect(source.items).toEqual([])
        expect(String(queried[0].name)).toBe('Koko')
    })

    test('queryset child deletes remove the row from the parent collection', async () => {
        const metadata = createMetadata({
            attributes: {
                delete: {namespace: 'callable'},
            },
        })
        mockOperationFetch({
            result: {},
            state: createState({instance_data: {id: 1, name: 'Koko'}}),
            policy: createPolicy({
                name: 'gorillas.1',
                attributes: ['id', 'name', 'delete'],
                original_signature: 'next-signature',
            }),
            metadata,
        })
        const object = new GlueQuerySetProxy({
            http: new GlueHttp(new GlueConfig()),
            name: 'gorillas',
            policy: createPolicy({
                name: 'gorillas',
                namespace: 'querySet',
                attributes: ['query_with_params'],
            }),
            state: {
                items: [
                    {
                        policy: createPolicy({
                            name: 'gorillas.1',
                            attributes: ['id', 'name', 'delete'],
                            identity: {target_pk: 1, pk_field_name: 'id'},
                        }),
                        state: createState({instance_data: {id: 1, name: 'Koko'}}),
                        metadata,
                    },
                    {
                        policy: createPolicy({
                            name: 'gorillas.2',
                            attributes: ['id', 'name', 'delete'],
                            identity: {target_pk: 2, pk_field_name: 'id'},
                        }),
                        state: createState({instance_data: {id: 2, name: 'Michael'}}),
                        metadata,
                    },
                ],
            },
            metadata,
        })
        const rows = object.items

        await rows[0].delete()

        expect(object.items.length).toBe(1)
        expect(object.items[0].$name).toBe('gorillas.2')
    })
})
