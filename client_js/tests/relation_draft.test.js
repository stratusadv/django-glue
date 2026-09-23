import {describe, expect, test} from "bun:test"
import GlueClient from "../src/client"
import {createEntry, objectsEnvelope} from "./testUtils"

const relationAddress = 'alpha#test.skills'

function relationEntry() {
    return createEntry({
        policy: {
            name: 'alpha.skills', namespace: 'querySet', address: relationAddress,
            attributes: ['query_with_params', 'new'], state_snapshot: {},
        },
        staticData: {callables: {
            query_with_params: {allowed_arguments: ['filter', 'order_by', 'slice', 'seek_key', 'with_total']},
            new: {allowed_arguments: ['initial'], returns_glue: true},
        }},
    })
}

function draftEntry(identity) {
    return createEntry({policy: {
        name: 'alpha.skills.None', address: `${relationAddress}["t1"]`,
        identity: {target_pk: null, ...identity}, state_snapshot: {name: 'Foraging'},
    }})
}

async function createDraft(client, draft) {
    client.http.sendAttributeRequest = async () => objectsEnvelope([
        {address: relationAddress, result: draft.address},
        draft,
    ])
    return client._registry.getProxy(relationAddress).new({name: 'Foraging'})
}

describe('relation draft save', () => {
    test('carries a refresh of the producing relation and reconciles its membership', async () => {
        const client = new GlueClient({objects: [relationEntry()]})
        const draft = draftEntry({relation: {owner_model_class_path: 'Gorilla', owner_pk: 1, relation_name: 'skills'}})
        const created = await createDraft(client, draft)
        const row = createEntry({policy: {
            name: 'alpha.skills.7', address: `${relationAddress}[7]`,
            identity: {target_pk: 7}, state_snapshot: {id: 7, name: 'Foraging'},
        }})
        const requests = []
        client.http.sendAttributeRequest = async request => {
            requests.push(request)
            return objectsEnvelope([
                {address: draft.address, result: {success: true, errors: {}}, effects: {messages: []}},
                {
                    address: relationAddress,
                    computed_data: {items: [row.address], seek_key: null, has_next: false, batch_size: 10},
                    result: null,
                    effects: {messages: []},
                },
                row,
            ])
        }

        await created.save()

        expect(requests).toHaveLength(1)
        expect(requests[0].attribute).toBe('save')
        expect(requests[0].companions.map(record => record.address)).toEqual([relationAddress])
        const relation = client._registry.getProxy(relationAddress)
        expect(relation.items.map(item => item.name)).toEqual(['Foraging'])
    })

    test('a draft from a root queryset saves alone', async () => {
        const client = new GlueClient({objects: [relationEntry()]})
        const created = await createDraft(client, draftEntry({}))
        const requests = []
        client.http.sendAttributeRequest = async request => {
            requests.push(request)
            return objectsEnvelope([
                {address: created._record.address, result: {success: true, errors: {}}, effects: {messages: []}},
            ])
        }

        await created.save()

        expect(requests[0].companions).toEqual([])
    })
})
