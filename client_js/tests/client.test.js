import {describe, expect, test} from "bun:test"
import GlueClient from "../src/client"
import {createManifest, createPolicyToken} from "./testUtils"

describe('GlueClient registry', () => {
    test('registers named and direct proxies from addressed manifests', () => {
        const named = createManifest()
        const direct = createManifest({
            policy: {
                name: 'dashboard',
                namespace: 'dashboard',
                address: 'dashboard#test',
                attributes: [],
                state_snapshot: {},
            },
            staticData: {fields: {}, callables: {}},
        })
        const client = new GlueClient({manifest_list: [named, direct]})

        expect(client.model.gorilla._record.address).toBe('gorilla#test')
        expect(client.dashboard._record.address).toBe('dashboard#test')
        expect(client.model.gorilla).toBe(client.model.gorilla)
    })

    test('rejects a manifest whose outer and signed addresses differ', () => {
        const manifest = createManifest()
        manifest.address = 'wrong#address'
        expect(() => new GlueClient({manifest_list: [manifest]})).toThrow('does not match')
    })

    test('reintroducing an address patches the stable proxy', () => {
        const client = new GlueClient({manifest_list: [createManifest()]})
        const held = client.model.gorilla
        client.loadManifests([createManifest({
            policy: {state_snapshot: {id: 1, name: 'Michael', birthday: '1973-03-01'}},
        })])

        expect(client.model.gorilla).toBe(held)
        expect(held.name).toBe('Michael')
    })

    test('binds child paths through the address registry', () => {
        const child = createManifest({
            policy: {
                name: 'parent',
                address: 'gorilla#test.parent',
                state_snapshot: {id: 2, name: 'Matata'},
                attributes: ['id', 'name'],
            },
            staticData: {fields: {
                id: {value_path: 'id', editable: false},
                name: {value_path: 'name', editable: false},
            }, callables: {}},
        })
        const parent = createManifest({
            policy: {children: {parent: child.address}},
            staticData: {children: {parent: {kind: 'model', nullable: true}}},
        })
        const client = new GlueClient({manifest_list: [parent, child]})

        expect(client.model.gorilla.parent).toBe(client._registry.getProxy(child.address))
        expect(client.model.gorilla.parent.$owner).toBe(client.model.gorilla)
    })

    test('keeps function proxies callable and filters declared parameters', async () => {
        const manifest = createManifest({
            policy: {
                name: 'add',
                namespace: 'function',
                address: 'add#test',
                attributes: ['execute'],
                state_snapshot: {},
            },
            staticData: {
                fields: {},
                callables: {execute: {allowed_arguments: ['kwargs']}},
                params: [{name: 'left'}, {name: 'right'}],
            },
        })
        const client = new GlueClient({manifest_list: [manifest]})
        let sent
        client.http.sendAttributeRequest = async request => {
            sent = request
            return {data: {result: {result: 12}}}
        }

        expect(await client.function.add({left: 5, right: 7, ignored: true})).toBe(12)
        expect(sent.kwargs).toEqual({left: 5, right: 7})
    })

    test('rejects direct and named registrations sharing a namespace', () => {
        const direct = createManifest({policy: {
            name: 'custom', namespace: 'custom', address: 'custom#test', attributes: [], state_snapshot: {},
        }})
        const named = createManifest({policy: {
            name: 'named', namespace: 'custom', address: 'named#test', attributes: [], state_snapshot: {},
        }})
        expect(() => new GlueClient({manifest_list: [direct, named]})).toThrow('already registered directly')
    })

    test('requires the new manifest keys', () => {
        expect(() => new GlueClient({manifest_list: [{
            is_glue_manifest: true,
            policy_token: createPolicyToken(),
            state: {},
            metadata: {},
        }]})).toThrow('address and policy_token')
    })
})
