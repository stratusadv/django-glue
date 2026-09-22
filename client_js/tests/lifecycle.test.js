import {describe, expect, test} from "bun:test"
import GlueClient from "../src/client"
import {attributeResponse, createEntry} from "./testUtils"

function modelClient() {
    const client = new GlueClient({objects: [createEntry()]})
    globalThis.Glue = client
    return client
}

describe('proxy lifecycle', () => {
    test('emits before and after listeners with the stable proxy', async () => {
        const client = modelClient()
        const proxy = client.model.gorilla
        const events = []
        proxy.addListener('save', event => events.push(['before', event.object]), 'before')
        proxy.addListener('save', event => events.push(['after', event.proxy]))
        client.http.sendAttributeRequest = async () => attributeResponse('gorilla#test', {result: {ok: true}})

        await proxy.save()

        expect(events).toEqual([['before', proxy], ['after', proxy]])
    })

    test('removes registered listeners', async () => {
        const client = modelClient()
        const proxy = client.model.gorilla
        let calls = 0
        const listener = () => calls++
        proxy.addListener('save', listener).removeListener('save', listener)
        client.http.sendAttributeRequest = async () => attributeResponse('gorilla#test', {result: null})

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

    test('notifies error listeners and keeps the operation rejected', async () => {
        const client = modelClient()
        const proxy = client.model.gorilla
        const events = []
        proxy.addListener('save', event => events.push(event), 'error')
        client.http.sendAttributeRequest = async () => {
            throw new Error('offline')
        }

        await expect(proxy.save()).rejects.toThrow('offline')
        expect(events).toHaveLength(1)
        expect(events[0].proxy).toBe(proxy)
    })

    test('does not treat untagged result objects as manifests', async () => {
        const client = modelClient()
        const result = {address: 'other#test', policy_token: 'not-a-token', value: 3}
        client.http.sendAttributeRequest = async () => attributeResponse('gorilla#test', {result})

        expect(await client.model.gorilla.save()).toEqual(result)
        expect(client._registry.getProxy('other#test')).toBeNull()
    })
})
