import {describe, expect, test} from "bun:test"
import GlueClient from "../src/client"
import {attributeResponse, createEntry, createPolicyToken, objectsEnvelope} from "./testUtils"

function querysetManifest(overrides = {}) {
    return createEntry({
        policy: {
            name: 'gorillas', namespace: 'querySet', address: 'gorillas#test',
            attributes: ['query_with_params', 'get', 'new', 'count'], state_snapshot: {},
            ...overrides.policy,
        },
        staticData: {callables: {
            query_with_params: {allowed_arguments: ['filter', 'order_by', 'slice', 'seek_key', 'with_total']},
            get: {allowed_arguments: ['pk'], returns_glue: true},
            new: {allowed_arguments: ['initial'], returns_glue: true},
            count: {allowed_arguments: ['filter']},
        }},
        ...overrides,
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

describe('queryset proxy facade', () => {
    test('hydrates eager initial items through the shared registry', () => {
        const first = row(1, 'Koko')
        const manifest = querysetManifest({
            computedData: {items: [first.address], seek_key: null, has_next: false, batch_size: null},
        })
        const client = new GlueClient({objects: [manifest, first]})

        expect(client.querySet.gorillas.items).toEqual([client._registry.getProxy(first.address)])
        expect(client.querySet.gorillas.items[0].name).toBe('Koko')
    })

    test('stores pagination data and appends the next batch', async () => {
        const client = new GlueClient({objects: [querysetManifest()]})
        const responses = [
            {items: [row(1, 'Koko')], seek_key: 'next', has_next: true, batch_size: 1, total: 2},
            {items: [row(2, 'Ndume')], seek_key: null, has_next: false, batch_size: 1},
        ]
        client.http.sendAttributeRequest = async () => {
            const page = responses.shift()
            const entries = page.items
            return objectsEnvelope([
                {address: 'gorillas#test', result: {...page, items: entries.map(entry => entry.address)}},
                ...entries,
            ])
        }
        const queryset = client.querySet.gorillas

        await queryset.all({withTotal: true})
        expect(queryset.items.map(item => item.name)).toEqual(['Koko'])
        expect(queryset.total).toBe(2)
        expect(queryset.batchSize).toBe(1)
        expect(queryset.hasNext).toBeTrue()

        await queryset.loadMore()
        expect(queryset.items.map(item => item.name)).toEqual(['Koko', 'Ndume'])
        expect(queryset.total).toBe(2)
        expect(queryset.hasNext).toBeFalse()
    })

    test('merges query parameters and caches canonical views', () => {
        const queryset = new GlueClient({objects: [querysetManifest()]}).querySet.gorillas
        const filtered = queryset.filter({active: true})
        const ordered = filtered.orderBy('-rank').slice(0, 10)

        expect(ordered._queryParams).toEqual({
            filter: {active: true}, order_by: '-rank', slice: {start: 0, stop: 10},
        })
        expect(queryset.filter({active: true})).toBe(filtered)
    })

    test('bounds the query-view cache', () => {
        const queryset = new GlueClient({objects: [querysetManifest()]}).querySet.gorillas

        for (let index = 0; index < 80; index++) queryset.filter({id: index})

        expect(queryset._queryCache.size).toBeLessThanOrEqual(64)
        expect(queryset._queryCache.get('{}')).toBe(queryset)
    })

    test('count sends the current filter only', async () => {
        const client = new GlueClient({objects: [querysetManifest()]})
        let request
        client.http.sendAttributeRequest = async value => {
            request = value
            return attributeResponse('gorillas#test', {result: 4})
        }

        const count = await client.querySet.gorillas.filter({active: true}).count()

        expect(count).toBe(4)
        expect(request.attribute).toBe('count')
        expect(request.kwargs).toEqual({filter: {active: true}})
    })

    test('get and query results reuse one proxy for the same address', async () => {
        const client = new GlueClient({objects: [querysetManifest()]})
        const first = row(1, 'Koko')
        client.http.sendAttributeRequest = async request => request.attribute === 'get'
            ? attributeResponse('gorillas#test', {result: first.address})
            : objectsEnvelope([
                {address: 'gorillas#test', result: {items: [first.address]}},
                first,
            ])
        const queryset = client.querySet.gorillas

        await queryset.all()
        const fromList = queryset.items[0]
        const fromGet = await queryset.get(1)

        expect(fromGet).toBe(fromList)
        // A row already live in the collection is not re-introduced by get;
        // its data stands as last acknowledged.
        expect(fromGet.name).toBe('Koko')
    })

    test('an unloaded loadMore call loads the first page', async () => {
        const client = new GlueClient({objects: [querysetManifest()]})
        let calls = 0
        client.http.sendAttributeRequest = async () => {
            calls++
            return attributeResponse('gorillas#test', {result: {items: [], has_next: false}})
        }

        await client.querySet.gorillas.loadMore()

        expect(calls).toBe(1)
        expect(client.querySet.gorillas._loaded).toBeTrue()
    })

    test('new returns the model proxy at the address the server responds with', async () => {
        const client = new GlueClient({objects: [querysetManifest()]})
        const draft = createEntry({policy: {
            name: 'gorillas.draft', address: 'gorillas#test.draft',
            identity: {target_pk: null}, state_snapshot: {name: ''},
        }})
        client.http.sendAttributeRequest = async request => {
            expect(request.kwargs).toEqual({initial: {name: 'Ndume'}})
            return objectsEnvelope([
                {address: 'gorillas#test', result: draft.address},
                draft,
            ])
        }

        const created = await client.querySet.gorillas.new({name: 'Ndume'})

        expect(created).toBe(client._registry.getProxy(draft.address))
        expect(created.name).toBe('')
    })
})

describe('formset proxy facade', () => {
    test('resolves forms from signed child addresses', () => {
        const form = createEntry({policy: {
            name: 'contacts.0', namespace: 'form', address: 'contacts#test[0]',
            identity: {target_pk: null}, state_snapshot: {name: 'Ada'},
        }})
        const formset = createEntry({
            policy: {
                name: 'contacts', namespace: 'formSet', address: 'contacts#test',
                identity: {}, attributes: ['append', 'validate'], state_snapshot: {},
                children: {'0': form.address},
            },
            staticData: {
                fields: {}, children: {'0': {kind: 'form', nullable: false}},
                callables: {append: {allowed_arguments: ['key', 'initial']}, validate: {allowed_arguments: []}},
            },
        })
        const client = new GlueClient({objects: [formset, form]})

        expect(client.formSet.contacts.forms).toEqual([client._registry.getProxy(form.address)])
        expect(client.formSet.contacts.length).toBe(1)
    })

    test('append introduces the returned form and advances membership', async () => {
        const formset = createEntry({
            policy: {
                name: 'contacts', namespace: 'formSet', address: 'contacts#test',
                identity: {}, attributes: ['append'], state_snapshot: {}, children: {},
            },
            staticData: {
                fields: {},
                children: {'0': {kind: 'form', nullable: false}},
                callables: {append: {allowed_arguments: ['key', 'initial'], returns_glue: true}},
            },
        })
        const client = new GlueClient({objects: [formset]})
        const form = createEntry({policy: {
            name: 'contacts.0', namespace: 'form', address: 'contacts#test[0]',
            identity: {target_pk: null}, state_snapshot: {name: 'Ada'},
        }})
        client.http.sendAttributeRequest = async () => objectsEnvelope([
            {
                address: 'contacts#test',
                policy_token: createPolicyToken({
                    name: 'contacts', namespace: 'formSet', address: 'contacts#test',
                    identity: {}, attributes: ['append'], state_snapshot: {},
                    children: {'0': form.address},
                }),
                result: form.address,
            },
            form,
        ])

        const appended = await client.formSet.contacts.append({name: 'Ada'})

        expect(appended).toBe(client._registry.getProxy(form.address))
        expect(client.formSet.contacts.forms).toEqual([appended])
    })

    test('validate exposes non-form errors', async () => {
        const formset = createEntry({
            policy: {
                name: 'contacts', namespace: 'formSet', address: 'contacts#test',
                identity: {}, attributes: ['validate'], state_snapshot: {}, children: {},
            },
            staticData: {fields: {}, callables: {validate: {allowed_arguments: []}}},
        })
        const client = new GlueClient({objects: [formset]})
        client.http.sendAttributeRequest = async () => attributeResponse('contacts#test', {
            result: {valid: false, non_form_errors: ['Need another contact']},
        })

        const result = await client.formSet.contacts.validate()

        expect(result.valid).toBeFalse()
        expect(client.formSet.contacts.nonFormErrors).toEqual(['Need another contact'])
    })
})
