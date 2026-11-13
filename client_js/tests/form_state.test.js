import {describe, expect, test} from "bun:test"
import GlueClient from "../src/client"
import {attributeResponse, createEntry, createPolicyToken} from "./testUtils"

const FILTERS = {search: null, styles: null, sort: 'name'}
const SORT_CHOICES = [{value: 'name', label: 'Name'}, {value: 'age', label: 'Age'}]

function roster() {
    const policy = {attributes: ['filters', 'save'], state_snapshot: {filters: FILTERS}}
    const client = new GlueClient({objects: [createEntry({
        policy,
        staticData: {value_attributes: {
            filters: {value_path: 'filters', editable: true, fields: {
                search: {type: 'CharField', label: 'Search', editable: true, widget: 'TextInput'},
                styles: {type: 'MultipleChoiceField', label: 'Styles', editable: true, widget: 'SelectMultiple', choices: []},
                sort: {type: 'ChoiceField', label: 'Sort', editable: true, widget: 'Select', choices: SORT_CHOICES},
            }},
        }},
    })]})
    const sent = []
    client.http.sendAttributeRequest = async (request) => {
        sent.push(request)
        return attributeResponse('gorilla#test', {
            policy_token: createPolicyToken({...policy, state_snapshot: {filters: request.updates.filters}}),
            computed_data: {value_attributes: {filters: {errors: [], field_errors: {sort: ['Pick a listed sort.']}}}},
            result: {},
        })
    }
    return {proxy: client.model.gorilla, sent}
}

describe('a form held as state (ADR 042)', () => {
    test('each of its fields is reached beside its value', () => {
        const {proxy} = roster()

        expect(proxy.filters.sort).toBe('name')
        expect(proxy.filters.$fields.sort.label).toBe('Sort')
        expect(proxy.filters.$fields.sort.choices.map(choice => choice.value)).toEqual(['name', 'age'])
        expect(proxy.filters.$fields.sort.value).toBe('name')
    })

    test('its fields are not part of the value it sends', () => {
        const {proxy} = roster()

        expect(Object.keys(proxy.filters)).toEqual(['search', 'styles', 'sort'])
        expect(proxy._record.captureRequest().updates).toEqual({})
    })

    test('changing one field sends the whole value', async () => {
        const {proxy, sent} = roster()
        proxy.filters.search = 'ko'
        proxy.filters.$fields.sort.value = 'age'

        await proxy.save()

        expect(sent[0].updates).toEqual({filters: {search: 'ko', styles: null, sort: 'age'}})
        expect(proxy.filters.sort).toBe('age')
    })

    test('a field reads its own errors from the answer', async () => {
        const {proxy} = roster()
        proxy.filters.sort = 'weight'

        await proxy.save()

        expect(proxy.filters.$fields.sort.errors).toEqual(['Pick a listed sort.'])
        expect(proxy.filters.$fields.search.errors).toEqual([])
    })
})
