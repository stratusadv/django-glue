import {describe, expect, test} from "bun:test"
import GlueClient from "../src/client"
import {attributeResponse, createEntry, createPolicyToken} from "./testUtils"

function model() {
    const client = new GlueClient({objects: [createEntry({
        computedData: {fields: {name: {errors: []}}},
    })]})
    return {client, proxy: client.model.gorilla}
}

describe('$refresh', () => {
    test('sends a call-less entry without updates and keeps local edits', async () => {
        const {client, proxy} = model()
        const requests = []
        client.http.sendAttributeRequest = async request => {
            requests.push(request)
            return attributeResponse('gorilla#test', {
                policy_token: createPolicyToken({
                    state_snapshot: {id: 1, name: 'Koko', birthday: '1980-01-01'},
                }),
                result: null,
                effects: {messages: []},
            })
        }
        proxy.name = 'Typing'

        const refreshed = await proxy.$refresh()

        expect(refreshed).toBe(proxy)
        expect(requests).toHaveLength(1)
        expect(requests[0].attribute).toBeNull()
        expect(requests[0].updates).toEqual({})
        expect(proxy.name).toBe('Typing')
        expect(proxy.birthday).toBe('1980-01-01')
    })

    test('submit sends pending edits for admission', async () => {
        const {client, proxy} = model()
        const requests = []
        client.http.sendAttributeRequest = async request => {
            requests.push(request)
            return attributeResponse('gorilla#test', {
                policy_token: createPolicyToken({
                    state_snapshot: {id: 1, name: 'Submitted', birthday: '1971-07-04'},
                }),
                result: null,
                effects: {messages: []},
            })
        }
        proxy.name = 'Submitted'

        await proxy.$refresh({submit: true})

        expect(requests[0].updates).toEqual({name: 'Submitted'})
        expect(proxy._record.canonical.name).toBe('Submitted')
    })

    test('queues behind an in-flight call on the same address', async () => {
        const {client, proxy} = model()
        const order = []
        let release
        client.http.sendAttributeRequest = async request => {
            order.push(request.attribute ?? 'refresh')
            if (request.attribute === 'save') await new Promise(resolve => { release = resolve })
            return attributeResponse('gorilla#test', {result: null, effects: {messages: []}})
        }

        const saving = proxy.save()
        const refreshing = proxy.$refresh()
        await Promise.resolve()
        expect(order).toEqual(['save'])
        release()
        await Promise.all([saving, refreshing])

        expect(order).toEqual(['save', 'refresh'])
    })
})
