import {describe, expect, test} from "bun:test"
import GlueClient from "../src/client"
import {GlueRelationAttribute} from "../src/proxies/attributes"
import {attributeResponse, createEntry, createPolicyToken} from "./testUtils"

describe('field-backed proxy facades', () => {
    test('exposes field errors, primitive conversion, and stable identity', () => {
        const client = new GlueClient({objects: [createEntry({
            computedData: {value_attributes: {name: {errors: ['Required']}}},
        })]})
        const proxy = client.model.gorilla
        const field = proxy.$fields.name

        expect(field.hasErrors).toBeTrue()
        expect(field.errorText).toBe('Required')
        expect(String(field)).toBe('Koko')
        expect(proxy.$pk).toBe(1)

        proxy.name = 'Ndume'
        expect(proxy.$fields.name).toBe(field)
        expect(field.value).toBe('Ndume')
    })

    test('uses the full static field path for computed errors', () => {
        const manifest = createEntry({
            policy: {state_snapshot: {profile_name: ''}},
            staticData: {value_attributes: {
                'profile.name': {value_path: 'profile_name', type: 'CharField', editable: true},
            }},
            computedData: {value_attributes: {'profile.name': {errors: ['Required']}}},
        })
        const proxy = new GlueClient({objects: [manifest]}).model.gorilla

        expect(proxy.$fields['profile.name'].errors).toEqual(['Required'])
        expect(proxy.profile.name).toBe('')
    })

    test('form proxies share the field-backed contract', () => {
        const form = createEntry({policy: {
            name: 'profile', namespace: 'form', address: 'profile#test',
            state_snapshot: {name: 'Koko'},
        }})
        const proxy = new GlueClient({objects: [form]}).form.profile

        proxy.$fields.name.value = 'Michael'

        expect(proxy.name).toBe('Michael')
        expect(proxy.hasErrors()).toBeFalse()
    })

    test('a derived value at path `fields` is a value, apart from presentation output', () => {
        const manifest = createEntry({
            policy: {
                name: 'profile', namespace: 'form', address: 'profile#test',
                state_snapshot: {name: 'Koko'},
            },
            staticData: {value_attributes: {fields: {value_path: 'fields', editable: false}}},
            computedData: {
                values: {fields: ['name', 'birthday']},
                value_attributes: {name: {errors: ['Required']}},
            },
        })
        const proxy = new GlueClient({objects: [manifest]}).form.profile

        expect(proxy.fields).toEqual(['name', 'birthday'])
        expect(proxy.$fields.name.errors).toEqual(['Required'])
        expect(proxy.$fields.fields.errors).toEqual([])
        expect(proxy.hasErrors()).toBeTrue()
    })

    test('choice fields expose single and multiple selection helpers', () => {
        const manifest = createEntry({
            policy: {state_snapshot: {status: 'open', tags: ['a']}},
            staticData: {value_attributes: {
                status: {
                    value_path: 'status', type: 'ChoiceField', editable: true,
                    choices: [{value: 'open', label: 'Open'}, {value: 'closed', label: 'Closed'}],
                },
                tags: {
                    value_path: 'tags', type: 'MultipleChoiceField', editable: true,
                    choices: [{value: 'a', label: 'A'}, {value: 'b', label: 'B'}],
                },
            }},
        })
        const fields = new GlueClient({objects: [manifest]}).model.gorilla.$fields

        expect(fields.status.selectedChoice.label).toBe('Open')
        fields.tags.toggleChoice('b')
        expect(fields.tags.selectedValues).toEqual(['a', 'b'])
        fields.tags.removeChoice('a')
        expect(fields.tags.selectedChoices.map(choice => choice.label)).toEqual(['B'])
    })

    test('relation fields load and share choices by cache key', async () => {
        GlueRelationAttribute.loadingCache.clear()
        const manifest = createEntry({
            policy: {
                state_snapshot: {skill: 1},
                attributes: ['skill', 'foreign_key_choices'],
            },
            staticData: {
                value_attributes: {skill: {
                    value_path: 'skill', type: 'ModelChoiceField', editable: true,
                    choice_model_path: 'app.Skill', choices_cache_key: 'skill-cache',
                }},
                callables: {foreign_key_choices: {allowed_arguments: ['field_name']}},
            },
        })
        const client = new GlueClient({objects: [manifest]})
        let calls = 0
        client.http.sendAttributeRequest = async request => {
            calls++
            expect(request.kwargs).toEqual({field_name: 'skill'})
            return attributeResponse('gorilla#test', {result: {results: [{value: 1, label: 'Climbing'}]}})
        }

        const first = client.model.gorilla.$fields.skill
        await first.ensureChoices()
        expect(first.selectedChoice.label).toBe('Climbing')
        expect(await first.ensureChoices()).toEqual([{value: 1, label: 'Climbing'}])
        expect(calls).toBe(1)
    })

    test('relation fields reload cached choices in server order and update shared fields', async () => {
        GlueRelationAttribute.loadingCache.clear()
        const firstEntry = createEntry({
            policy: {
                name: 'first_gorilla', address: 'first_gorilla#test',
                state_snapshot: {skill: 1},
                attributes: ['skill', 'foreign_key_choices'],
            },
            staticData: {
                value_attributes: {skill: {
                    value_path: 'skill', type: 'ModelChoiceField', editable: true,
                    choice_model_path: 'app.Skill', choices_cache_key: 'reload-skill-cache',
                }},
                callables: {foreign_key_choices: {allowed_arguments: ['field_name']}},
            },
        })
        const secondEntry = createEntry({
            policy: {
                name: 'second_gorilla', address: 'second_gorilla#test',
                state_snapshot: {skill: null},
                attributes: ['skill', 'foreign_key_choices'],
            },
            staticData: {
                value_attributes: {skill: {
                    value_path: 'skill', type: 'ModelChoiceField', editable: true,
                    choice_model_path: 'app.Skill', choices_cache_key: 'reload-skill-cache',
                }},
                callables: {foreign_key_choices: {allowed_arguments: ['field_name']}},
            },
        })
        const client = new GlueClient({objects: [firstEntry, secondEntry]})
        let serverChoices = [{value: 1, label: 'Climbing'}]
        let calls = 0
        client.http.sendAttributeRequest = async request => {
            calls++
            return attributeResponse(request.address, {result: {results: serverChoices}})
        }

        const first = client.model.first_gorilla.$fields.skill
        const second = client.model.second_gorilla.$fields.skill
        await first.ensureChoices()
        await second.ensureChoices()
        expect(calls).toBe(1)

        serverChoices = [
            {value: 2, label: 'Bouldering'},
            {value: 1, label: 'Climbing'},
        ]
        const reloaded = await first.reloadChoices()

        expect(calls).toBe(2)
        expect(reloaded).toEqual(serverChoices)
        expect(first.choices).toEqual(serverChoices)
        expect(second.choices).toEqual(serverChoices)

        await second.ensureChoices()
        expect(calls).toBe(2)
    })

    test('stale ensureChoices and overlapping reloadChoices ignore superseded responses', async () => {
        GlueRelationAttribute.loadingCache.clear()
        const entries = ['first', 'second', 'third'].map(prefix => createEntry({
            policy: {
                name: `${prefix}_gorilla`,
                address: `${prefix}_gorilla#test`,
                state_snapshot: {skill: 1},
                attributes: ['skill', 'foreign_key_choices'],
            },
            staticData: {
                value_attributes: {skill: {
                    value_path: 'skill', type: 'ModelChoiceField', editable: true,
                    choice_model_path: 'app.Skill', choices_cache_key: 'race-skill-cache',
                }},
                callables: {foreign_key_choices: {allowed_arguments: ['field_name']}},
            },
        }))
        const client = new GlueClient({objects: entries})
        const pending = []
        client.http.sendAttributeRequest = request => new Promise(resolve => {
            pending.push({address: request.address, resolve})
        })

        const first = client.model.first_gorilla.$fields.skill
        const second = client.model.second_gorilla.$fields.skill
        const third = client.model.third_gorilla.$fields.skill
        const ensurePromise = first.ensureChoices()
        const firstReload = second.reloadChoices()
        const secondReload = third.reloadChoices()
        await Promise.resolve()
        expect(pending).toHaveLength(3)

        // Newest reload resolves first.
        pending[2].resolve(attributeResponse(pending[2].address, {result: {results: [{value: 3, label: 'Newest'}]}}))
        await secondReload
        expect(first.choices).toEqual([{value: 3, label: 'Newest'}])
        expect(second.choices).toEqual([{value: 3, label: 'Newest'}])
        expect(third.choices).toEqual([{value: 3, label: 'Newest'}])

        // Earlier ensureChoices and first reload settle afterwards and must be ignored.
        pending[0].resolve(attributeResponse(pending[0].address, {result: {results: [{value: 1, label: 'Stale Ensure'}]}}))
        pending[1].resolve(attributeResponse(pending[1].address, {result: {results: [{value: 2, label: 'Stale Reload'}]}}))
        await Promise.all([ensurePromise, firstReload])

        expect(first.choices).toEqual([{value: 3, label: 'Newest'}])
        expect(second.choices).toEqual([{value: 3, label: 'Newest'}])
        expect(third.choices).toEqual([{value: 3, label: 'Newest'}])
    })

    test('failed reloadChoices preserves prior loaded choices and does not reset loaded flag', async () => {
        GlueRelationAttribute.loadingCache.clear()
        const manifest = createEntry({
            policy: {
                state_snapshot: {skill: 1},
                attributes: ['skill', 'foreign_key_choices'],
            },
            staticData: {
                value_attributes: {skill: {
                    value_path: 'skill', type: 'ModelChoiceField', editable: true,
                    choice_model_path: 'app.Skill', choices_cache_key: 'failed-reload-cache',
                }},
                callables: {foreign_key_choices: {allowed_arguments: ['field_name']}},
            },
        })
        const client = new GlueClient({objects: [manifest]})
        let calls = 0
        client.http.sendAttributeRequest = async () => {
            calls++
            if (calls === 1) {
                return attributeResponse('gorilla#test', {result: {results: [{value: 1, label: 'Climbing'}]}} )
            }
            throw new Error('Server unavailable')
        }

        const field = client.model.gorilla.$fields.skill
        await field.ensureChoices()
        expect(field.choices).toEqual([{value: 1, label: 'Climbing'}])

        await expect(field.reloadChoices()).rejects.toThrow('Server unavailable')

        expect(field.choices).toEqual([{value: 1, label: 'Climbing'}])
        expect(calls).toBe(2)
        await field.ensureChoices()
        expect(calls).toBe(2)
    })

    test('search results retain a selected relation after search clears', async () => {
        GlueRelationAttribute.loadingCache.clear()
        const manifest = createEntry({
            policy: {
                state_snapshot: {skill: null},
                attributes: ['skill', 'foreign_key_choices'],
            },
            staticData: {
                value_attributes: {skill: {
                    value_path: 'skill', type: 'ModelChoiceField', editable: true,
                    choice_model_path: 'app.Skill', choices_cache_key: 'search-cache',
                }},
                callables: {foreign_key_choices: {allowed_arguments: ['field_name', 'search']}},
            },
        })
        const client = new GlueClient({objects: [manifest]})
        client.http.sendAttributeRequest = async () => attributeResponse('gorilla#test', {
            result: {results: [{value: 2, label: 'Drumming'}]},
        })
        const field = client.model.gorilla.$fields.skill

        await field.searchChoices('Drum')
        field.value = 2
        field.clearSearch()

        expect(field.selectedChoice).toEqual({value: 2, label: 'Drumming'})
    })

    test('overridden relation choices survive a response that refreshes the field', async () => {
        GlueRelationAttribute.loadingCache.clear()
        const manifest = createEntry({
            policy: {
                state_snapshot: {project: 93},
                attributes: ['project', 'project_is_billable'],
            },
            staticData: {
                value_attributes: {project: {
                    value_path: 'project', type: 'ModelChoiceField', editable: true,
                    choices: [], choice_model_path: 'app.Project',
                }},
                callables: {project_is_billable: {allowed_arguments: ['project_id']}},
            },
        })
        const client = new GlueClient({objects: [manifest]})
        client.http.sendAttributeRequest = async () => attributeResponse('gorilla#test', {result: false})
        const proxy = client.model.gorilla
        const field = proxy.$fields.project

        field.overrideChoices([{value: 93, label: 'Enterprise CRM'}])
        await proxy.project_is_billable({project_id: 93})

        expect(proxy.$fields.project).toBe(field)
        expect(field.choices).toEqual([{value: 93, label: 'Enterprise CRM'}])
        expect(field.selectedChoice.label).toBe('Enterprise CRM')
    })

    test('static replacement removes obsolete fields and callables', () => {
        const client = new GlueClient({objects: [createEntry()]})
        const proxy = client.model.gorilla
        const replacement = {
            address: 'gorilla#test',
            policy_token: createPolicyToken({
                address: 'gorilla#test', attributes: ['name'], state_snapshot: {name: 'Koko'},
            }),
            static_data: {
                value_attributes: {name: {value_path: 'name', type: 'CharField', editable: true}},
            },
            computed_data: {},
        }

        client.loadObjects([replacement])

        expect('birthday' in proxy).toBeFalse()
        expect('save' in proxy).toBeFalse()
        expect(proxy.$fields.birthday).toBeUndefined()
    })

    test('exposes a stable key from the primary key, falling back to the name', () => {
        const row = new GlueClient({objects: [createEntry({})]}).model.gorilla

        expect(row.$key).toBe(1)

        const draft = new GlueClient({objects: [createEntry({policy: {
            name: 'new_gorilla', address: 'new_gorilla#test',
            identity: {target_pk: null}, state_snapshot: {name: ''},
        }})]}).model.new_gorilla

        expect(draft.$pk).toBeUndefined()
        expect(draft.$key).toBe('new_gorilla')
    })

    test('relation multiple-choice fields expose pk-based selection helpers', async () => {
        GlueRelationAttribute.loadingCache.clear()
        const manifest = createEntry({
            policy: {
                state_snapshot: {skills: [1]},
                attributes: ['skills', 'foreign_key_choices'],
            },
            staticData: {
                value_attributes: {skills: {
                    value_path: 'skills', type: 'ManyToManyField', editable: true,
                    choice_model_path: 'app.Skill', choices_cache_key: 'skills-cache',
                }},
                callables: {foreign_key_choices: {allowed_arguments: ['field_name']}},
            },
        })
        const client = new GlueClient({objects: [manifest]})
        client.http.sendAttributeRequest = async () => attributeResponse('gorilla#test', {result: {results: [
            {value: 1, label: 'Climbing'},
            {value: 2, label: 'Grappling'},
        ]}})
        const field = client.model.gorilla.$fields.skills

        expect(field.selectedPks).toEqual([1])
        expect(field.hasChoiceSelected(1)).toBeTrue()
        expect(field.hasChoiceSelected(2)).toBeFalse()

        await field.ensureChoices()
        expect(field.selectedChoices.map(choice => choice.label)).toEqual(['Climbing'])
        field.addChoice(2)
        expect(field.selectedPks).toEqual([1, 2])
        field.addChoice(2)
        expect(field.selectedPks).toEqual([1, 2])
        expect(field.selectedChoices.map(choice => choice.label)).toEqual(['Climbing', 'Grappling'])
        field.toggleChoice(1)
        expect(field.selectedPks).toEqual([2])
        expect(field.selectedChoices.map(choice => choice.label)).toEqual(['Grappling'])
        expect(field.hasChoiceSelected(1)).toBeFalse()
    })
})
