import {describe, expect, test} from "bun:test"
import GlueClient from "../src/client"
import {attributeResponse, createEntry} from "./testUtils"

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
        static_data: {fields: {}, callables: {}, ...staticData},
    })
}

function tallyClient({listeners = [COUNTED], mounted = true} = {}) {
    const tally = componentEntry({address: TALLY, staticData: {listeners}})
    const card = componentEntry({
        address: CARD,
        ancestors: [TALLY],
        attributes: ['increment'],
        staticData: {
            callables: {increment: {allowed_arguments: []}},
            events: ['counted'],
            event_ids: {counted: COUNTED},
        },
    })
    const client = new GlueClient({objects: [tally, card]})
    globalThis.Glue = client
    document.body.innerHTML = mounted
        ? `<div data-glue-address="${TALLY}"><p id="summary">0 counts</p><div data-glue-address="${CARD}">card 0</div></div>`
        : `<div data-glue-address="${CARD}">card 0</div>`
    return {client, card: client._registry.getProxy(CARD), cardToken: card.policy_token}
}

function respond(client, {tally}) {
    const requests = []
    client.http.sendAttributeRequest = async request => {
        requests.push(request)
        if (request.address === CARD) {
            return attributeResponse(CARD, {
                result: null,
                html: `<div data-glue-address="${CARD}">card 1</div>`,
                effects: {messages: [], events: [{name: 'counted', detail: {value: 1}}]},
            })
        }
        return attributeResponse(TALLY, {result: null, effects: {messages: []}, ...tally})
    }
    return requests
}

describe('component listeners', () => {
    test('delivers a descendant event to the listening ancestor with the source token', async () => {
        const {client, card, cardToken} = tallyClient()
        const requests = respond(client, {tally: {
            html: `<div data-glue-address="${TALLY}"><p id="summary">1 counts</p><div data-glue-address="${CARD}">card 1</div></div>`,
        }})

        await card.increment()

        expect(requests.map(request => [request.address, request.attribute])).toEqual([
            [CARD, 'increment'],
            [TALLY, '$receive'],
        ])
        expect(requests[1].kwargs).toEqual({
            events: [{event: COUNTED, source_token: cardToken, detail: {value: 1}}],
        })
        expect(document.querySelector('#summary').textContent).toBe('1 counts')
        expect(document.querySelector(`[data-glue-address="${CARD}"]`).textContent).toBe('card 1')
    })

    test('the source morphs itself when the listener does not re-render', async () => {
        const {client, card} = tallyClient()
        respond(client, {tally: {}})

        await card.increment()

        expect(document.querySelector('#summary').textContent).toBe('0 counts')
        expect(document.querySelector(`[data-glue-address="${CARD}"]`).textContent).toBe('card 1')
    })

    test('an ancestor without a listener for the event is not called', async () => {
        const {client, card} = tallyClient({listeners: ['other.Component.event']})
        const requests = respond(client, {tally: {}})

        await card.increment()

        expect(requests.map(request => request.attribute)).toEqual(['increment'])
    })

    test('an ancestor that is not mounted is not called', async () => {
        const {client, card} = tallyClient({mounted: false})
        const requests = respond(client, {tally: {}})

        await card.increment()

        expect(requests.map(request => request.attribute)).toEqual(['increment'])
    })

    test('a component that re-renders on the event hears it from a sibling, a listener does not', async () => {
        const {client, card} = tallyClient({listeners: []})
        const panel = componentEntry({address: 'panel#test', staticData: {rerender_on: [COUNTED]}})
        const bystander = componentEntry({address: 'other#test', staticData: {listeners: [COUNTED]}})
        client.loadObjects([panel, bystander])
        document.body.insertAdjacentHTML(
            'beforeend',
            '<div data-glue-address="panel#test"></div><div data-glue-address="other#test"></div>',
        )
        const requests = respond(client, {tally: {}})

        await card.increment()

        expect(requests.map(request => [request.address, request.attribute])).toEqual([
            [CARD, 'increment'],
            ['panel#test', '$receive'],
        ])
    })

    test('a component call reports the component roots mounted inside it', async () => {
        const {client} = tallyClient()
        const requests = respond(client, {tally: {}})

        await client._registry.getProxy(TALLY).$refresh()

        expect(requests[0].mounted).toEqual([CARD])
    })

    test("a listener's own event travels on to its ancestor", async () => {
        const TALLIED = 'gorilla.components.CounterTallyComponent.tallied'
        const page = componentEntry({address: 'page#test', staticData: {listeners: [TALLIED]}})
        const tally = componentEntry({
            address: TALLY,
            ancestors: ['page#test'],
            staticData: {listeners: [COUNTED], events: ['tallied'], event_ids: {tallied: TALLIED}},
        })
        const card = componentEntry({
            address: CARD,
            ancestors: [TALLY, 'page#test'],
            attributes: ['increment'],
            staticData: {
                callables: {increment: {allowed_arguments: []}},
                events: ['counted'],
                event_ids: {counted: COUNTED},
            },
        })
        const client = new GlueClient({objects: [page, tally, card]})
        globalThis.Glue = client
        document.body.innerHTML = `<div data-glue-address="page#test"><div data-glue-address="${TALLY}"><div data-glue-address="${CARD}"></div></div></div>`
        const requests = []
        client.http.sendAttributeRequest = async request => {
            requests.push([request.address, request.attribute, request.kwargs?.events?.map(({event}) => event)])
            const events = {
                [CARD]: [{name: 'counted', detail: {}}],
                [TALLY]: [{name: 'tallied', detail: {}}],
            }[request.address] || []
            return attributeResponse(request.address, {result: null, effects: {messages: [], events}})
        }

        await client._registry.getProxy(CARD).increment()

        expect(requests).toEqual([
            [CARD, 'increment', undefined],
            [TALLY, '$receive', [COUNTED]],
            ['page#test', '$receive', [TALLIED]],
        ])
    })

    test('a failed delivery still applies the source morph and resolves the source call', async () => {
        const {client, card} = tallyClient()
        const errors = []
        client.onError(({error}) => errors.push(error.message))
        respond(client, {tally: {error: {code: 'not_authorized', message: 'denied'}}})

        await card.increment()

        expect(document.querySelector(`[data-glue-address="${CARD}"]`).textContent).toBe('card 1')
        expect(errors).toEqual([`Glue request for address "${TALLY}" failed: denied`])
    })
})

describe('$dispatch', () => {
    test('reaches $on listeners and the page with no request when no component reacts', async () => {
        const {client, card} = tallyClient({listeners: []})
        const requests = respond(client, {tally: {}})
        const heard = []
        const bubbled = []
        card.$on('counted', event => heard.push([event.type, event.detail, event.source === card]))
        document.body.addEventListener('counted', event => bubbled.push(event.detail), {once: true})

        await card.$dispatch('counted', {value: 3})

        expect(requests).toEqual([])
        expect(heard).toEqual([['counted', {value: 3, $address: CARD}, true]])
        expect(bubbled).toEqual([{value: 3, $address: CARD}])
    })

    test('tells a component that reacts to the event, as a fired event does', async () => {
        const {client, card, cardToken} = tallyClient()
        const requests = respond(client, {tally: {}})

        await card.$dispatch('counted', {value: 3})

        expect(requests.map(request => [request.address, request.attribute])).toEqual([
            [TALLY, '$receive'],
        ])
        expect(requests[0].kwargs).toEqual({
            events: [{event: COUNTED, source_token: cardToken, detail: {value: 3}}],
        })
    })

    test('refuses an event the object does not declare', async () => {
        const {card} = tallyClient()

        await expect(card.$dispatch('cancelled')).rejects.toThrow(
            'Event "cancelled" is not declared on this Glue object.',
        )
    })

    test('raises a declared event on an object that is not a component', async () => {
        const entry = createEntry({
            policy: {name: 'koko', address: 'koko#test'},
            staticData: {events: ['saved']},
        })
        const client = new GlueClient({objects: [entry]})
        const model = client._registry.getProxy(entry.address)
        const heard = []
        model.$on('saved', event => heard.push(event.detail))

        await model.$dispatch('saved', {pk: 7})

        expect(heard).toEqual([{pk: 7, $address: 'koko#test'}])
    })
})
