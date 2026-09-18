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

function identityManifest(overrides = {}) {
    return {
        is_glue_manifest: true,
        policy_token: createPolicyToken(),
        state: createState(),
        metadata: createMetadata(),
        ...overrides,
    }
}

const renamedManifest = () => identityManifest({
    state: createState({instance_data: {id: 1, name: 'Renamed'}}),
})

const settle = () => new Promise(resolve => setTimeout(resolve, 25))

describe('GlueClient proxy identity', () => {
    test('named proxies are one shared instance per name', () => {
        const client = new GlueClient({manifest_list: [identityManifest()]})

        expect(client.model.gorilla).toBe(client.model.gorilla)
    })

    test('direct namespace proxies are one shared instance', () => {
        const client = new GlueClient({
            manifest_list: [identityManifest({
                policy_token: createPolicyToken({
                    name: 'timeEntryDashboard',
                    namespace: 'timeEntryDashboard',
                    attributes: [],
                }),
                state: {},
                metadata: {attributes: {}},
            })],
        })

        expect(client.timeEntryDashboard).toBe(client.timeEntryDashboard)
    })

    test('function proxies are one shared instance', () => {
        const client = new GlueClient({
            manifest_list: [identityManifest({
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
            })],
        })

        expect(client.function.add).toBe(client.function.add)
    })

    test('handed-out proxies are Alpine reactive proxies', () => {
        const client = new GlueClient({manifest_list: [identityManifest()]})
        const proxy = client.model.gorilla

        // Alpine.reactive returns a reactive proxy unchanged, and wraps anything else.
        expect(globalThis.Alpine.reactive(proxy)).toBe(proxy)
    })

    test('re-registering a name updates the existing instance in place', () => {
        const client = new GlueClient({manifest_list: [identityManifest()]})
        const held = client.model.gorilla

        client.loadManifests([renamedManifest()])

        expect(client.model.gorilla).toBe(held)
        expect(held.name).toBe('Renamed')
    })

    test('an action-returned manifest resolves as a reactive unregistered proxy', () => {
        const client = new GlueClient({manifest_list: []})
        const resolved = client.resolveManifest(identityManifest())

        expect(resolved.name).toBe('Koko')
        expect(globalThis.Alpine.reactive(resolved)).toBe(resolved)
        expect(client.model).toBeUndefined()
    })

    test('a fresh lazy manifest lets a held model recover from a failed load', async () => {
        const client = new GlueClient({manifest_list: [identityManifest({state: {}})]})
        const held = client.model.gorilla
        client.http.sendAttributeRequest = async () => { throw new Error('Offline') }

        await held._ensureLoaded()
        expect(held._loadError.message).toBe('Offline')

        client.loadManifests([identityManifest({state: {}})])
        client.http.sendAttributeRequest = async () => ({data: {state: renamedManifest().state}})
        await held._ensureLoaded()

        expect(held.name).toBe('Renamed')
        expect(held._loadError).toBeNull()
    })

    test('a reference held in an Alpine scope observes re-registration (GLUE-93)', async () => {
        const client = new GlueClient({manifest_list: [identityManifest()]})
        // What an x-data scope holds: resolved once, kept for the scope's life.
        const held = client.model.gorilla
        let observed
        globalThis.Alpine.effect(() => {
            observed = held.name
        })
        await settle()
        expect(observed).toBe('Koko')

        client.loadManifests([renamedManifest()])
        await settle()

        expect(observed).toBe('Renamed')
    })
})

describe('GlueClient with bundled Alpine', () => {
    function withoutAlpine(readyState, run) {
        const alpine = globalThis.Alpine
        delete globalThis.Alpine
        Object.defineProperty(document, 'readyState', {value: readyState, configurable: true})

        try {
            return run()
        } finally {
            delete document.readyState
            globalThis.Alpine = alpine
        }
    }

    test('constructing the client does not need Alpine', () => {
        withoutAlpine('loading', () => {
            expect(() => new GlueClient({manifest_list: [identityManifest()]})).not.toThrow()
        })
    })

    test('proxies are reactive before DOM initialization', () => {
        withoutAlpine('loading', () => {
            const client = new GlueClient({manifest_list: [identityManifest()]})
            expect(client.model.gorilla.name).toBe('Koko')
            expect(client.model.gorilla).toBe(client.model.gorilla)
        })
    })

    test('early references observe manifests registered before DOM initialization', () => {
        let client
        let held
        withoutAlpine('loading', () => {
            client = new GlueClient({manifest_list: [identityManifest()]})
            held = client.model.gorilla
            expect(() => client.loadManifests([renamedManifest()])).not.toThrow()
        })

        expect(client.model.gorilla.name).toBe('Renamed')
        expect(client.model.gorilla).toBe(held)
    })

    test('proxies do not require an external Alpine global', () => {
        withoutAlpine('complete', () => {
            const client = new GlueClient({manifest_list: [identityManifest()]})

            expect(client.model.gorilla.name).toBe('Koko')
        })
    })
})
