import {describe, expect, test} from "bun:test"
import GlueClient from "../src/client"
import {createEntry} from "./testUtils"

const COUNTED = 'gorilla.components.CounterCardComponent.counted'
const TALLY = 'tally#test'
const CARD = 'tally#test[card]'

function componentEntry({address, ancestors = [], staticData = {}, attributes = []}) {
    return createEntry({
        policy: {
            name: address, namespace: 'component', address,
            identity: {component_id: 'test', parameters: {}, ancestors},
            attributes, state_snapshot: {},
        },
        static_data: {value_attributes: {}, callables: {}, ...staticData},
    })
}

function tallyClient({cardEvents = true} = {}) {
    const tally = componentEntry({address: TALLY, staticData: {listeners: [COUNTED]}})
    const card = componentEntry({
        address: CARD,
        ancestors: [TALLY],
        attributes: ['increment'],
        staticData: {
            callables: {increment: {allowed_arguments: []}},
            ...(cardEvents ? {events: ['counted'], event_ids: {counted: COUNTED}} : {}),
        },
    })
    const client = new GlueClient({objects: [tally, card]})
    globalThis.Glue = client
    document.body.innerHTML = `<div data-glue-address="${TALLY}"><p id="summary">0 counts</p><div data-glue-address="${CARD}">card 0</div></div>`
    return {client, card: client._registry.getProxy(CARD), tally: client._registry.getProxy(TALLY)}
}

const TALLY_HTML = `<div data-glue-address="${TALLY}"><p id="summary">1 counts</p><div data-glue-address="${CARD}">card 1</div></div>`

// The card's call answers with its own entry, then, when `answer` is given, the
// tally's answer as the server puts it after the call's (ADR 044).
function respond(client, {answer = null} = {}) {
    const requests = []
    client.http.sendAttributeRequest = async request => {
        requests.push(request)
        if (request.address === CARD) {
            const objects = [{
                address: CARD,
                result: 1,
                effects: {messages: [], events: [{name: 'counted', detail: {value: 1}}]},
            }]
            if (answer && request.receivers?.some(receiver => receiver.address === TALLY)) objects.push(answer)
            return {data: {objects}}
        }
        return {data: {objects: [{address: TALLY, result: null, html: TALLY_HTML, effects: {messages: []}}]}}
    }
    return requests
}

describe('receivers answered in the call that emits (ADR 044)', () => {
    test('a call names the mounted objects that react to an event its object declares', async () => {
        const {client, card, tally} = tallyClient()
        const requests = respond(client)

        await card.increment()

        expect(requests[0].receivers).toEqual([
            {address: TALLY, policyToken: tally._record.policyToken, updates: {}, mounted: [CARD]},
        ])
    })

    test('an answered receiver re-renders from the call\'s response, with no request of its own', async () => {
        const {client, card} = tallyClient()
        const requests = respond(client, {answer: {address: TALLY, result: null, html: TALLY_HTML, effects: {messages: []}}})

        await card.increment()

        expect(requests.map(request => [request.address, request.attribute])).toEqual([[CARD, 'increment']])
        expect(document.querySelector('#summary').textContent).toBe('1 counts')
    })

    test('a receiver the response did not answer is delivered to with a request, as before', async () => {
        const {client, card} = tallyClient()
        const requests = respond(client)

        await card.increment()

        expect(requests.map(request => [request.address, request.attribute])).toEqual([
            [CARD, 'increment'],
            [TALLY, '$receive'],
        ])
        expect(document.querySelector('#summary').textContent).toBe('1 counts')
    })

    test('a receiver answered with an error is delivered to with a request', async () => {
        const {client, card} = tallyClient()
        const requests = respond(client, {answer: {address: TALLY, error: {code: 'policy_expired', message: 'expired'}}})

        await card.increment()

        expect(requests.map(request => [request.address, request.attribute])).toEqual([
            [CARD, 'increment'],
            [TALLY, '$receive'],
        ])
    })

    test('a call on an object that declares no events names no receivers', async () => {
        const {client, card} = tallyClient({cardEvents: false})
        const requests = respond(client)

        await card.increment()

        expect(requests[0].receivers).toEqual([])
    })

    test('a receiver with a call of its own in flight is not named, and is delivered to after it', async () => {
        const {client, card, tally} = tallyClient()
        let release
        const held = new Promise(resolve => { release = resolve })
        tally._record.enqueue(() => held)
        const requests = respond(client, {answer: {address: TALLY, result: null, html: TALLY_HTML, effects: {messages: []}}})

        const increment = card.increment()
        await Promise.resolve()
        release()
        await increment

        expect(requests[0].receivers).toEqual([])
        expect(requests.map(request => [request.address, request.attribute])).toEqual([
            [CARD, 'increment'],
            [TALLY, '$receive'],
        ])
    })
})
