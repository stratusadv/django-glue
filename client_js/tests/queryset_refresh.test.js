import {describe, expect, test} from "bun:test"
import GlueClient from "../src/client"
import {createEntry, createPolicyToken, objectsEnvelope} from "./testUtils"

const querysetPolicy = {
    name: 'gorillas', namespace: 'querySet', address: 'gorillas#test',
    attributes: ['query_with_params', 'count'], state_snapshot: {},
}

function querysetEntry() {
    return createEntry({
        policy: querysetPolicy,
        staticData: {callables: {
            query_with_params: {allowed_arguments: ['filter', 'order_by', 'slice', 'seek_key', 'with_total']},
            count: {allowed_arguments: ['filter']},
        }},
    })
}

function row(id, name) {
    return createEntry({policy: {
        name: `gorillas.${id}`,
        address: `gorillas#test[${id}]`,
        identity: {target_pk: id, pk_field_name: 'id'},
        state_snapshot: {id, name},
    }})
}

function signedQueryToken(filter) {
    return createPolicyToken({
        ...querysetPolicy,
        state_snapshot: {last_query_params: {filter, order_by: null}, loaded_row_count: 1},
    })
}

function page(rows, extra = {}) {
    return {items: rows.map(entry => entry.address), seek_key: null, has_next: false, batch_size: 10, ...extra}
}

describe('queryset $refresh', () => {
    test('routes refreshed rows only to the view matching the signed query', async () => {
        const client = new GlueClient({objects: [querysetEntry()]})
        const queryset = client.querySet.gorillas
        const active = queryset.filter({active: true})
        const koko = row(1, 'Koko')
        const ndume = row(2, 'Ndume')
        client.http.sendAttributeRequest = async request => {
            if (request.attribute === 'query_with_params') {
                return objectsEnvelope([
                    {address: 'gorillas#test', policy_token: signedQueryToken({active: true}), result: page([koko])},
                    koko,
                ])
            }
            return objectsEnvelope([
                {address: 'gorillas#test', computed_data: page([koko, ndume]), result: null, effects: {messages: []}},
                ndume,
            ])
        }

        await active.all()
        const refreshed = await active.$refresh()

        expect(refreshed).toBe(active)
        expect(active.items.map(item => item.name)).toEqual(['Koko', 'Ndume'])
        expect(queryset.items).toEqual([])
    })

    test('a later rowless response does not re-sync stale rows', async () => {
        const koko = row(1, 'Koko')
        const ndume = row(2, 'Ndume')
        const client = new GlueClient({objects: [
            createEntry({
                policy: querysetPolicy,
                staticData: {callables: {
                    query_with_params: {allowed_arguments: ['seek_key']},
                    count: {allowed_arguments: ['filter']},
                }},
                computedData: page([koko], {has_next: true, seek_key: 'next'}),
            }),
            koko,
        ]})
        const queryset = client.querySet.gorillas
        client.http.sendAttributeRequest = async request => (
            request.attribute === 'count'
                ? objectsEnvelope([{address: 'gorillas#test', result: 2, effects: {messages: []}}])
                : objectsEnvelope([{address: 'gorillas#test', result: page([ndume])}, ndume])
        )

        await queryset.loadMore()
        await queryset.count()

        expect(queryset.items.map(item => item.name)).toEqual(['Koko', 'Ndume'])
    })

    test('a view other than the signed query re-queries itself', async () => {
        const client = new GlueClient({objects: [querysetEntry()]})
        const queryset = client.querySet.gorillas
        const inactive = queryset.filter({active: false})
        const requests = []
        client.http.sendAttributeRequest = async request => {
            requests.push(request)
            return objectsEnvelope([
                {address: 'gorillas#test', policy_token: signedQueryToken({active: false}), result: page([])},
            ])
        }

        await inactive.$refresh()

        expect(requests).toHaveLength(1)
        expect(requests[0].attribute).toBe('query_with_params')
        expect(requests[0].kwargs.filter).toEqual({active: false})
    })
})
