import {describe, expect, test} from "bun:test"
import GlueClient from "../src/client"
import {RelationFieldGlue} from "../src/proxies/fields"
import {createManifest, createPolicyToken} from "./testUtils"

describe('field-backed proxy facades', () => {
    test('exposes field errors, primitive conversion, and stable identity', () => {
        const client = new GlueClient({manifest_list: [createManifest({
            computedData: {fields: {name: {errors: ['Required']}}},
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
        const manifest = createManifest({
            policy: {state_snapshot: {profile_name: ''}},
            staticData: {fields: {
                'profile.name': {value_path: 'profile_name', type: 'CharField', editable: true},
            }},
            computedData: {fields: {'profile.name': {errors: ['Required']}}},
        })
        const proxy = new GlueClient({manifest_list: [manifest]}).model.gorilla

        expect(proxy.$fields['profile.name'].errors).toEqual(['Required'])
        expect(proxy.profile.name).toBe('')
    })

    test('form proxies share the field-backed contract', () => {
        const form = createManifest({policy: {
            name: 'profile', namespace: 'form', address: 'profile#test',
            state_snapshot: {name: 'Koko'},
        }})
        const proxy = new GlueClient({manifest_list: [form]}).form.profile

        proxy.$fields.name.value = 'Michael'

        expect(proxy.name).toBe('Michael')
        expect(proxy.hasErrors()).toBeFalse()
    })

    test('choice fields expose single and multiple selection helpers', () => {
        const manifest = createManifest({
            policy: {state_snapshot: {status: 'open', tags: ['a']}},
            staticData: {fields: {
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
        const fields = new GlueClient({manifest_list: [manifest]}).model.gorilla.$fields

        expect(fields.status.selectedChoice.label).toBe('Open')
        fields.tags.toggleChoice('b')
        expect(fields.tags.selectedValues).toEqual(['a', 'b'])
        fields.tags.removeChoice('a')
        expect(fields.tags.selectedChoices.map(choice => choice.label)).toEqual(['B'])
    })

    test('relation fields load and share choices by cache key', async () => {
        RelationFieldGlue.loadingCache.clear()
        const manifest = createManifest({
            policy: {
                state_snapshot: {skill: 1},
                attributes: ['skill', 'foreign_key_choices'],
            },
            staticData: {
                fields: {skill: {
                    value_path: 'skill', type: 'ModelChoiceField', editable: true,
                    choice_model_path: 'app.Skill', choices_cache_key: 'skill-cache',
                }},
                callables: {foreign_key_choices: {allowed_arguments: ['field_name']}},
            },
        })
        const client = new GlueClient({manifest_list: [manifest]})
        let calls = 0
        client.http.sendAttributeRequest = async request => {
            calls++
            expect(request.kwargs).toEqual({field_name: 'skill'})
            return {data: {result: {results: [{value: 1, label: 'Climbing'}]}}}
        }

        const first = client.model.gorilla.$fields.skill
        await first.ensureChoices()
        expect(first.selectedChoice.label).toBe('Climbing')
        expect(await first.ensureChoices()).toEqual([{value: 1, label: 'Climbing'}])
        expect(calls).toBe(1)
    })

    test('search results retain a selected relation after search clears', async () => {
        RelationFieldGlue.loadingCache.clear()
        const manifest = createManifest({
            policy: {
                state_snapshot: {skill: null},
                attributes: ['skill', 'foreign_key_choices'],
            },
            staticData: {
                fields: {skill: {
                    value_path: 'skill', type: 'ModelChoiceField', editable: true,
                    choice_model_path: 'app.Skill', choices_cache_key: 'search-cache',
                }},
                callables: {foreign_key_choices: {allowed_arguments: ['field_name', 'search']}},
            },
        })
        const client = new GlueClient({manifest_list: [manifest]})
        client.http.sendAttributeRequest = async () => ({data: {
            result: {results: [{value: 2, label: 'Drumming'}]},
        }})
        const field = client.model.gorilla.$fields.skill

        await field.searchChoices('Drum')
        field.value = 2
        field.clearSearch()

        expect(field.selectedChoice).toEqual({value: 2, label: 'Drumming'})
    })

    test('lazy value access starts one load attempt and retry starts another', async () => {
        const manifest = createManifest({
            policy: {
                attributes: ['rank', 'load_state'],
                state_snapshot: {},
            },
            staticData: {
                fields: {rank: {value_path: 'rank', type: 'IntegerField', editable: false}},
                callables: {load_state: {allowed_arguments: []}},
            },
            loading_strategy: 'lazy',
        })
        const client = new GlueClient({manifest_list: [manifest]})
        let calls = 0
        client.http.sendAttributeRequest = async () => {
            calls++
            if (calls === 1) throw new Error('offline')
            return {data: {computed_data: {rank: 700}, result: {}}}
        }
        const proxy = client.model.gorilla

        void proxy.rank
        void proxy.rank
        await proxy._loadPromise
        expect(calls).toBe(1)
        expect(proxy._loadError.message).toBe('offline')

        await proxy.retryLoad()
        expect(calls).toBe(2)
        expect(proxy.rank).toBe(700)
    })

    test('static replacement removes obsolete fields and callables', () => {
        const client = new GlueClient({manifest_list: [createManifest()]})
        const proxy = client.model.gorilla
        const replacement = {
            is_glue_manifest: true,
            address: 'gorilla#test',
            policy_token: createPolicyToken({
                address: 'gorilla#test', attributes: ['name'], state_snapshot: {name: 'Koko'},
            }),
            static_data: {
                fields: {name: {value_path: 'name', type: 'CharField', editable: true}},
            },
            computed_data: {},
            loading_strategy: 'eager',
        }

        client.loadManifests([replacement])

        expect('birthday' in proxy).toBeFalse()
        expect('save' in proxy).toBeFalse()
        expect(proxy.$fields.birthday).toBeUndefined()
    })

    test('exposes a stable key from the primary key, falling back to the name', () => {
        const row = new GlueClient({manifest_list: [createManifest({})]}).model.gorilla

        expect(row.$key).toBe(1)

        const draft = new GlueClient({manifest_list: [createManifest({policy: {
            name: 'new_gorilla', address: 'new_gorilla#test',
            identity: {target_pk: null}, state_snapshot: {name: ''},
        }})]}).model.new_gorilla

        expect(draft.$pk).toBeUndefined()
        expect(draft.$key).toBe('new_gorilla')
    })

    test('relation multiple-choice fields expose pk-based selection helpers', async () => {
        RelationFieldGlue.loadingCache.clear()
        const manifest = createManifest({
            policy: {
                state_snapshot: {skills: [1]},
                attributes: ['skills', 'foreign_key_choices'],
            },
            staticData: {
                fields: {skills: {
                    value_path: 'skills', type: 'ManyToManyField', editable: true,
                    choice_model_path: 'app.Skill', choices_cache_key: 'skills-cache',
                }},
                callables: {foreign_key_choices: {allowed_arguments: ['field_name']}},
            },
        })
        const client = new GlueClient({manifest_list: [manifest]})
        client.http.sendAttributeRequest = async () => ({data: {result: {results: [
            {value: 1, label: 'Climbing'},
            {value: 2, label: 'Grappling'},
        ]}}})
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
