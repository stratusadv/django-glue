import {describe, expect, test} from "bun:test"
import GlueClient from "../src/client"
import GlueConfig from "../src/config"
import GlueHttp from "../src/http"
import {attributeResponse, createEntry, mockOperationFetch} from "./testUtils"

const CARD = 'card#test'

function formEntry(path, {access = 'change'} = {}) {
    return createEntry({
        policy: {
            name: path, namespace: 'form', address: `${CARD}.${path}`, access,
            state_snapshot: {name: 'Ada'}, attributes: ['name'],
        },
        staticData: {fields: {name: {value_path: 'name', editable: true}}},
    })
}

function cardClient({children, slots}) {
    const card = createEntry({
        policy: {
            name: CARD, namespace: 'component', address: CARD,
            identity: {component_id: 'test', parameters: {}, ancestors: []},
            attributes: ['send'], state_snapshot: {},
            children: Object.fromEntries(Object.entries(children).map(([path, entry]) => [path, entry.address])),
        },
        static_data: {fields: {}, callables: {send: {allowed_arguments: []}}, children: slots},
    })
    const client = new GlueClient({objects: [card, ...Object.values(children)]})
    const requests = []
    client.http.sendAttributeRequest = async request => {
        requests.push(request)
        return attributeResponse(CARD, {result: null, effects: {messages: []}})
    }
    return {client, proxy: client._registry.getProxy(CARD), requests}
}

describe('child submissions', () => {
    test('a component call carries its declared children with their tokens and unsaved changes', async () => {
        const contact = formEntry('contact')
        const {client, proxy, requests} = cardClient({
            children: {contact},
            slots: {contact: {kind: 'form', nullable: false, submits_with_owner: true}},
        })
        client._registry.getProxy(contact.address).name = 'Bee'

        await proxy.send()

        expect(requests[0].childSubmissions).toEqual({
            contact: {policy_token: contact.policy_token, updates: {name: 'Bee'}},
        })
    })

    test('a child declared as a property is not submitted', async () => {
        const contact = formEntry('contact')
        const {proxy, requests} = cardClient({
            children: {contact},
            slots: {contact: {kind: 'form', nullable: false}},
        })

        await proxy.send()

        expect(requests[0].childSubmissions).toBeUndefined()
    })

    test('a view-only child is not submitted', async () => {
        const terms = formEntry('terms', {access: 'view'})
        const {proxy, requests} = cardClient({
            children: {terms},
            slots: {terms: {kind: 'form', nullable: false, submits_with_owner: true}},
        })

        await proxy.send()

        expect(requests[0].childSubmissions).toBeUndefined()
    })

    test('a refresh carries no children, because no call reads them', async () => {
        const contact = formEntry('contact')
        const {proxy, requests} = cardClient({
            children: {contact},
            slots: {contact: {kind: 'form', nullable: false, submits_with_owner: true}},
        })

        await proxy.$refresh()

        expect(requests[0].childSubmissions).toBeUndefined()
    })

    test('a formset child is submitted with its rows', async () => {
        const row = createEntry({
            policy: {
                name: 'lines.0', namespace: 'form', address: `${CARD}.lines[0]`,
                state_snapshot: {name: 'Ada'}, attributes: ['name'],
            },
            staticData: {fields: {name: {value_path: 'name', editable: true}}},
        })
        const lines = createEntry({
            policy: {
                name: 'lines', namespace: 'formSet', address: `${CARD}.lines`,
                attributes: [], state_snapshot: {}, children: {0: row.address},
            },
            staticData: {fields: {}, callables: {}},
        })
        const {client, proxy, requests} = cardClient({
            children: {lines},
            slots: {lines: {kind: 'formSet', nullable: false, submits_with_owner: true}},
        })
        client.loadObjects([row])
        client._registry.getProxy(row.address).name = 'Bee'

        await proxy.send()

        expect(requests[0].childSubmissions.lines).toEqual({
            policy_token: lines.policy_token,
            updates: {},
            forms: {0: {policy_token: row.policy_token, updates: {name: 'Bee'}}},
        })
    })

    test('the request entry names the submissions child_submissions', async () => {
        const calls = mockOperationFetch()
        const http = new GlueHttp(new GlueConfig())

        await http.sendAttributeRequest({
            address: CARD,
            policyToken: 't',
            attribute: 'send',
            childSubmissions: {contact: {policy_token: 'c', updates: {name: 'Bee'}}},
        })

        expect(JSON.parse(calls[0].options.body.get('objects'))[0].child_submissions).toEqual({
            contact: {policy_token: 'c', updates: {name: 'Bee'}},
        })
    })
})
