import {describe, expect, test} from "bun:test"
import GlueClient from "../src/client"
import {attributeResponse, createEntry, createPolicyToken} from "./testUtils"

const SORT_CHOICES = [{value: 'name', label: 'Name'}, {value: 'age', label: 'Age'}]

function roster() {
    const policy = {
        name: 'roster', namespace: 'component', address: 'roster#test',
        attributes: ['sort', 'load_items'], state_snapshot: {sort: 'name'},
    }
    const client = new GlueClient({objects: [createEntry({
        policy,
        staticData: {
            value_attributes: {
                sort: {
                    value_path: 'sort', namespace: 'field', type: 'TypedChoiceField', label: 'Sort by',
                    required: true, editable: true, disabled: false, widget: 'Select', choices: SORT_CHOICES,
                },
            },
            callables: {load_items: {allowed_arguments: []}},
        },
    })]})
    const sent = []
    client.http.sendAttributeRequest = async (request) => {
        sent.push(request)
        return attributeResponse('roster#test', {
            policy_token: createPolicyToken({...policy, state_snapshot: {sort: request.updates.sort}}),
            result: {},
        })
    }
    return {proxy: client._registry.getProxy('roster#test'), sent}
}

describe('a form field as a component attribute\'s type (ADR 051)', () => {
    test('the component describes it under $fields', () => {
        const {proxy} = roster()

        expect(proxy.$fields.sort.label).toBe('Sort by')
        expect(proxy.$fields.sort.required).toBe(true)
        expect(proxy.$fields.sort.choices.map(choice => choice.value)).toEqual(['name', 'age'])
        expect(proxy.$fields.sort.value).toBe('name')
    })

    test('the value is read beside its description', () => {
        const {proxy} = roster()

        expect(proxy.sort).toBe('name')
    })

    test('choosing through its description sends the value', async () => {
        const {proxy, sent} = roster()
        proxy.$fields.sort.value = 'age'

        await proxy.load_items()

        expect(sent[0].updates).toEqual({sort: 'age'})
        expect(proxy.sort).toBe('age')
    })
})
