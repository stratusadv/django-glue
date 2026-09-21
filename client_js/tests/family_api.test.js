import {describe, expect, test} from "bun:test"
import GlueClient from "../src/client"
import {createManifest} from "./testUtils"

describe('family proxy facades', () => {
    test('sequence items resolve from signed child addresses', () => {
        const item = createManifest({policy: {
            name: 'days.monday', address: 'days#test[monday]', state_snapshot: {id: 1, name: 'Monday'},
        }})
        const sequence = createManifest({
            policy: {
                name: 'days', namespace: 'sequence', address: 'days#test',
                identity: {item_keys: ['monday']}, attributes: [], state_snapshot: {},
                children: {monday: item.address},
            },
            staticData: {fields: {}, callables: {}},
        })
        const client = new GlueClient({manifest_list: [sequence, item]})
        expect(client.sequence.days.items).toEqual([client._registry.getProxy(item.address)])
        expect(client.sequence.days.at(0).name).toBe('Monday')
    })

    test('queryset result manifests enter the shared registry', async () => {
        const queryset = createManifest({
            policy: {
                name: 'gorillas', namespace: 'querySet', address: 'gorillas#test',
                attributes: ['query_with_params'], state_snapshot: {},
            },
            staticData: {fields: {}, callables: {query_with_params: {allowed_arguments: []}}},
            loading_strategy: 'lazy',
        })
        const row = createManifest({policy: {
            name: 'gorillas.1', address: 'gorillas#test[1]', state_snapshot: {id: 1, name: 'Koko'},
        }})
        const client = new GlueClient({manifest_list: [queryset]})
        client.http.sendAttributeRequest = async () => ({data: {
            result: {items: [row], seek_key: null, has_next: false, batch_size: null},
        }})

        await client.querySet.gorillas.all()
        expect(client.querySet.gorillas.items[0]).toBe(client._registry.getProxy(row.address))
    })

    test('query views share transport while keeping independent result sets', async () => {
        const queryset = createManifest({
            policy: {
                name: 'gorillas', namespace: 'querySet', address: 'gorillas#test',
                attributes: ['query_with_params'], state_snapshot: {},
            },
            staticData: {fields: {}, callables: {query_with_params: {allowed_arguments: []}}},
        })
        const client = new GlueClient({manifest_list: [queryset]})
        let kwargs
        client.http.sendAttributeRequest = async request => {
            kwargs = request.kwargs
            return {data: {result: {items: []}}}
        }

        const filtered = client.querySet.gorillas.filter({name__icontains: 'ko'}).orderBy('name')
        await filtered.all()
        expect(kwargs).toEqual({filter: {name__icontains: 'ko'}, order_by: 'name'})
        expect(filtered).not.toBe(client.querySet.gorillas)
    })
})
