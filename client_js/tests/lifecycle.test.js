import {describe, expect, test} from "bun:test"
import GlueConfig from "../src/config"
import GlueHttp from "../src/http"
import GlueModelProxy from "../src/proxies/model"
import {createMetadata, createPolicy, createState} from "./testUtils"

describe('proxy lifecycle behavior', () => {
    test('emits before and after listeners with the active proxy', async () => {
        global.fetch = async () => new Response(JSON.stringify({
            result: {ok: true}, state: createState(), policy: createPolicy(), metadata: createMetadata(), messages: [],
        }), {status: 200, headers: {'Content-Type': 'application/json'}})
        const proxy = new GlueModelProxy({
            http: new GlueHttp(new GlueConfig()),
            policy: createPolicy({attributes: ['id', 'save']}),
            state: createState(),
            metadata: createMetadata({attributes: {save: {namespace: 'callable'}}}),
        })
        const events = []
        proxy.addListener('save', event => events.push(['before', event.proxy]), 'before')
        proxy.addListener('save', event => events.push(['after', event.proxy]))

        await proxy.save()

        expect(events.map(event => event[0])).toEqual(['before', 'after'])
        expect(events[0][1]).toBeUndefined()
        expect(events[1][1]).toBe(proxy)
    })

    test('handles messages through the proxy message callback', async () => {
        global.fetch = async () => new Response(JSON.stringify({
            result: null, state: {}, policy: {}, metadata: {}, messages: [{level: 'success', message: 'Saved'}],
        }), {status: 200, headers: {'Content-Type': 'application/json'}})
        const proxy = new GlueModelProxy({
            http: new GlueHttp(new GlueConfig()),
            policy: createPolicy({attributes: ['save']}),
            state: {},
            metadata: createMetadata({attributes: {save: {namespace: 'callable'}}}),
        })
        const messages = []
        proxy.onMessage(payload => messages.push(payload.messages))

        await proxy.save()

        expect(messages).toEqual([[{level: 'success', message: 'Saved'}]])
    })
})
