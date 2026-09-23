import {describe, expect, test} from "bun:test"
import GlueClient from "../src/client"
import {attributeResponse, createEntry, objectsEnvelope} from "./testUtils"

describe('family proxy facades', () => {
    test('sequence items resolve from signed child addresses', () => {
        const item = createEntry({policy: {
            name: 'days.monday', address: 'days#test[monday]', state_snapshot: {id: 1, name: 'Monday'},
        }})
        const sequence = createEntry({
            policy: {
                name: 'days', namespace: 'sequence', address: 'days#test',
                identity: {item_keys: ['monday']}, attributes: [], state_snapshot: {},
                children: {monday: item.address},
            },
            staticData: {fields: {}, callables: {}},
        })
        const client = new GlueClient({objects: [sequence, item]})
        expect(client.sequence.days.items).toEqual([client._registry.getProxy(item.address)])
        expect(client.sequence.days.at(0).name).toBe('Monday')
    })

    test('queryset item addresses resolve through the shared registry', async () => {
        const queryset = createEntry({
            policy: {
                name: 'gorillas', namespace: 'querySet', address: 'gorillas#test',
                attributes: ['query_with_params'], state_snapshot: {},
            },
            staticData: {fields: {}, callables: {query_with_params: {allowed_arguments: []}}},
        })
        const row = createEntry({policy: {
            name: 'gorillas.1', address: 'gorillas#test[1]', state_snapshot: {id: 1, name: 'Koko'},
        }})
        const client = new GlueClient({objects: [queryset]})
        client.http.sendAttributeRequest = async () => objectsEnvelope([
            {address: 'gorillas#test', result: {
                items: [row.address], seek_key: null, has_next: false, batch_size: null,
            }},
            row,
        ])

        await client.querySet.gorillas.all()
        expect(client.querySet.gorillas.items[0]).toBe(client._registry.getProxy(row.address))
    })

    test('query views share transport while keeping independent result sets', async () => {
        const queryset = createEntry({
            policy: {
                name: 'gorillas', namespace: 'querySet', address: 'gorillas#test',
                attributes: ['query_with_params'], state_snapshot: {},
            },
            staticData: {fields: {}, callables: {query_with_params: {allowed_arguments: []}}},
        })
        const client = new GlueClient({objects: [queryset]})
        let kwargs
        client.http.sendAttributeRequest = async request => {
            kwargs = request.kwargs
            return attributeResponse('gorillas#test', {result: {items: []}})
        }

        const filtered = client.querySet.gorillas.filter({name__icontains: 'ko'}).orderBy('name')
        await filtered.all()
        expect(kwargs).toEqual({filter: {name__icontains: 'ko'}, order_by: 'name'})
        expect(filtered).not.toBe(client.querySet.gorillas)
    })
})
