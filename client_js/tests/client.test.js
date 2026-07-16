import {describe, expect, test} from "bun:test"
import GlueClient from "../src/client"
import {createPolicy, createMetadata, createState} from "./testUtils"

describe('GlueClient', () => {
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
                    policy: createPolicy(),
                    state: createState(),
                    metadata: createMetadata(),
                },
            ],
        })

        expect(client.http._config.attributeUrlPath).toBe('/custom/attribute/')
        expect(client.http._config.glueViewUrlPath).toBe('/custom/view/')
        expect(client.http._config.requestTimeoutSeconds).toBe(45)
        expect(client.proxy('gorilla')).toBe(client.model.gorilla)
        expect(client.model.gorilla.$name).toBe('gorilla')
        expect(String(client.model.gorilla.name)).toBe('Koko')
        expect(client.model.gorilla.name.value).toBe('Koko')
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
                policy: createPolicy({
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
                    policy: createPolicy({
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
