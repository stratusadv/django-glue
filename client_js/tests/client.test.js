import {describe, expect, test} from "bun:test"
import GlueClient from "../src/client"
import {createManifest, createPolicy, createPolicyToken, createMetadata, createState} from "./testUtils"

describe('GlueClient', () => {
    test('exposes client-level callbacks, fetch, and view helpers', async () => {
        happyDOM.setURL('http://localhost/')
        const client = new GlueClient({manifest_list: []})
        const onMessage = () => {}
        const onError = () => {}
        let fetchedUrl
        global.fetch = async url => {
            fetchedUrl = url
            return new Response(JSON.stringify({type: 'success'}), {status: 200})
        }

        expect(client.onMessage(onMessage)).toBe(client)
        expect(client.onError(onError)).toBe(client)
        expect(await client.fetch('/health')).toEqual({type: 'success'})
        expect(fetchedUrl).toBe('/health')
        expect(client.view('/partial/').url).toBe('/partial/')
    })

    test('registers proxies by name and policy namespace', () => {
        const client = new GlueClient({
            urls: {
                callable_attribute: '/custom/attribute/',
                glue_view: '/custom/view/',
            },
            config: {
                requestTimeoutSeconds: 45,
            },
            manifest_list: [
                {
                    is_glue_manifest: true,
                    policy_token: createPolicyToken(),
                    state: createState(),
                    metadata: createMetadata(),
                },
            ],
        })

        expect(client.http._config.attributeUrlPath).toBe('/custom/attribute/')
        expect(client.http._config.glueViewUrlPath).toBe('/custom/view/')
        expect(client.http._config.requestTimeoutSeconds).toBe(45)
        expect(client.model.gorilla._name).toBe('gorilla')
    })

    test('registers namespace-named proxies directly on the namespace', () => {
        const client = new GlueClient({
            manifest_list: [
                {
                    is_glue_manifest: true,
                    policy_token: createPolicyToken({
                        name: 'timeEntryDashboard',
                        namespace: 'timeEntryDashboard',
                        attributes: [],
                    }),
                    state: {},
                    metadata: {attributes: {}},
                },
            ],
        })

        expect(client.timeEntryDashboard._name).toBe('timeEntryDashboard')
    })

    test('rejects direct and named proxies sharing a namespace', () => {
        const directManifest = {
            is_glue_manifest: true,
            policy_token: createPolicyToken({
                name: 'timeEntryDashboard',
                namespace: 'timeEntryDashboard',
                attributes: [],
            }),
            state: {},
            metadata: {attributes: {}},
        }
        const namedManifest = {
            is_glue_manifest: true,
            policy_token: createPolicyToken({
                name: 'dashboard',
                namespace: 'timeEntryDashboard',
                attributes: [],
            }),
            state: {},
            metadata: {attributes: {}},
        }

        expect(() => new GlueClient({
            manifest_list: [directManifest, namedManifest],
        })).toThrow('already registered directly')

        expect(() => new GlueClient({
            manifest_list: [namedManifest, directManifest],
        })).toThrow('already registered')
    })

    test('creates proxy from manifest without registering', () => {
        const client = new GlueClient({manifest_list: []})
        const proxy = client._createProxy({
            policy: createPolicy({
                name: 'time_entry_days',
                namespace: 'sequence',
                identity: {},
                attributes: [],
            }),
            state: {},
            metadata: {attributes: {}},
        })

        expect(proxy._name).toBe('time_entry_days')
        // Should NOT be registered on the client namespace
        expect(client.sequence).toBeUndefined()
    })

    test('registers function proxies as callables', async () => {
        let capturedAttribute = null
        let capturedKwargs = null
        global.fetch = async (_, options) => {
            capturedAttribute = options.body.get('attribute')
            capturedKwargs = JSON.parse(options.body.get('kwargs'))
            return new Response(JSON.stringify({
                result: {result: 12},
                state: {},
                policy_token: createPolicyToken({
                    namespace: 'function',
                    identity: {params: ['left', 'right']},
                    attributes: ['execute'],
                }),
                metadata: {
                    namespace: 'function',
                    params: ['left', 'right'],
                    attributes: {execute: {namespace: 'callable'}},
                },
                messages: [],
            }))
        }

        const client = new GlueClient({
            manifest_list: [
                {
                    is_glue_manifest: true,
                    policy_token: createPolicyToken({
                        name: 'add',
                        namespace: 'function',
                        identity: {params: ['left', 'right']},
                        attributes: ['execute'],
                    }),
                    state: {},
                    metadata: {
                        namespace: 'function',
                        params: ['left', 'right'],
                        attributes: {execute: {namespace: 'callable'}},
                    },
                },
            ],
        })

        const result = await client.function.add({left: 5, right: 7, ignored: true})

        expect(result).toBe(12)
        expect(capturedAttribute).toBe('execute')
        expect(capturedKwargs).toEqual({left: 5, right: 7})
    })
})

describe('GlueClient proxy identity', () => {
    function manifest(overrides = {}) {
        return {
            is_glue_manifest: true,
            policy_token: createPolicyToken(),
            state: createState(),
            metadata: createMetadata(),
            ...overrides,
        }
    }

    test('named proxies are constructed per access', () => {
        const client = new GlueClient({manifest_list: [manifest()]})

        // Proxies are built on every property access so they are constructed
        // after Alpine's initTree and get wrapped in Alpine's reactive proxy.
        // The intended idiom is to resolve once into x-data and hold that
        // reference. See docs/roadmap/proxy_instance_management.md.
        expect(client.model.gorilla).not.toBe(client.model.gorilla)
    })

    test('re-registering a name is picked up by the next access', () => {
        const client = new GlueClient({manifest_list: [manifest()]})
        const before = client.model.gorilla.name

        client.loadManifests([manifest({state: createState({instance_data: {id: 1, name: 'Renamed'}})})])

        expect(before).not.toBe('Renamed')
        expect(client.model.gorilla.name).toBe('Renamed')
    })

    test('a proxy resolved before re-registration keeps its old state (GLUE-93)', () => {
        const client = new GlueClient({manifest_list: [manifest()]})
        // What an x-data scope holds: resolved once, kept for the scope's life.
        const held = client.model.gorilla

        client.loadManifests([manifest({state: createState({instance_data: {id: 1, name: 'Renamed'}})})])

        // Known gap: _registerManifest only replaces the manifest captured by
        // the accessor's getter, so an already-handed-out proxy is never
        // updated. Tracked as GLUE-93; flip this to 'Renamed' when it is fixed.
        expect(held.name).toBe('Koko')
        expect(client.model.gorilla.name).toBe('Renamed')
    })
})
