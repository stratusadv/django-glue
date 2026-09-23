import {describe, expect, test} from "bun:test"
import GlueClient from "../src/client"
import {attributeResponse, createEntry} from "./testUtils"

function modelClient() {
    const client = new GlueClient({objects: [createEntry({staticData: {events: ['saved']}})]})
    globalThis.Glue = client
    return client
}

describe('proxy lifecycle', () => {
    test('delivers declared events after the addressed response applies', async () => {
        const client = modelClient()
        const proxy = client.model.gorilla
        const events = []
        proxy.$on('saved', event => events.push([event.source, proxy.name]))
        client.http.sendAttributeRequest = async () => attributeResponse('gorilla#test', {
            result: {ok: true},
            computed_data: {name: 'Updated'},
            effects: {events: [{name: 'saved', detail: {pk: 1}}]},
        })

        await proxy.save()

        expect(events).toEqual([[proxy, 'Updated']])
    })

    test('removes registered listeners', async () => {
        const client = modelClient()
        const proxy = client.model.gorilla
        let calls = 0
        const listener = () => calls++
        const stop = proxy.$on('saved', listener)
        stop()
        client.http.sendAttributeRequest = async () => attributeResponse('gorilla#test', {
            result: null,
            effects: {events: [{name: 'saved', detail: {}}]},
        })

        await proxy.save()

        expect(calls).toBe(0)
    })

    test('routes messages through a proxy handler before the global handler', async () => {
        const client = modelClient()
        const proxy = client.model.gorilla
        const local = []
        const global = []
        client.onMessage(event => global.push(event))
        proxy.onMessage(event => local.push(event))
        client.http.sendAttributeRequest = async () => attributeResponse('gorilla#test', {
            result: null,
            effects: {messages: [{level: 'success', message: 'Saved'}]},
        })

        await proxy.save()

        expect(local).toHaveLength(1)
        expect(local[0].proxy).toBe(proxy)
        expect(global).toEqual([])
    })

    test('does not deliver events when an operation fails', async () => {
        const client = modelClient()
        const proxy = client.model.gorilla
        const events = []
        proxy.$on('saved', event => events.push(event))
        client.http.sendAttributeRequest = async () => {
            throw new Error('offline')
        }

        await expect(proxy.save()).rejects.toThrow('offline')
        expect(events).toHaveLength(0)
    })

    test('does not treat untagged result objects as manifests', async () => {
        const client = modelClient()
        const result = {address: 'other#test', policy_token: 'not-a-token', value: 3}
        client.http.sendAttributeRequest = async () => attributeResponse('gorilla#test', {result})

        expect(await client.model.gorilla.save()).toEqual(result)
        expect(client._registry.getProxy('other#test')).toBeNull()
    })
})
