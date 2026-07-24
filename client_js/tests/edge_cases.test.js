import {describe, expect, test} from "bun:test"
import GlueConfig from "../src/config"
import GlueHttp from "../src/http"
import GlueClient from "../src/client"
import GlueModelProxy from "../src/proxies/model"
import GlueQuerySetProxy from "../src/proxies/queryset"
import GlueView from "../src/view"
import {GlueProxyError} from "../src/errors"
import {createMetadata, createPolicy, createState} from "./testUtils"

function http() {
    return new GlueHttp(new GlueConfig())
}

describe('frontend edge cases', () => {
    test('client rejects invalid manifests', () => {
        expect(() => new GlueClient({manifest_list: [{policy: {namespace: 'model'}}]})).toThrow(GlueProxyError)
        expect(() => new GlueClient({manifest_list: [{policy: {name: 'bad', namespace: 'unknown'}}]})).toThrow(GlueProxyError)
    })

    test('proxy error listeners receive failed attribute requests', async () => {
        global.fetch = async () => new Response(JSON.stringify({error: {message: 'Failed'}}), {status: 500})
        const proxy = new GlueModelProxy({
            http: http(),
            policy: createPolicy({attributes: ['save']}),
            state: {},
            metadata: createMetadata({attributes: {save: {namespace: 'callable'}}}),
        })
        let received
        proxy.onError(payload => { received = payload })

        expect(await proxy.save()).toBeUndefined()
        expect(received.attribute).toBe('save')
        expect(received.proxy).toBe(proxy)
        expect(received.error.status).toBe(500)
    })

    test('model deletion removes the proxy from its collection', async () => {
        global.fetch = async () => new Response(JSON.stringify({
            result: null, state: {}, policy: {}, metadata: {},
        }), {status: 200, headers: {'Content-Type': 'application/json'}})
        const collection = new GlueQuerySetProxy({
            http: http(),
            policy: createPolicy({name: 'gorillas', namespace: 'querySet', attributes: []}),
            state: {items: []},
            metadata: {},
        })
        const row = new GlueModelProxy({
            http: http(),
            policy: createPolicy({name: 'gorillas.1', attributes: ['id', 'delete']}),
            state: createState({instance_data: {id: 1}}),
            metadata: createMetadata({attributes: {delete: {namespace: 'callable'}}}),
        })
        row.$collection = collection
        collection._modelProxies.set(row._name, row)

        await row.delete()

        expect(collection._modelProxies.has('gorillas.1')).toBe(false)
    })

    test('choice and many-relation fields expose selection helpers', () => {
        const object = new GlueModelProxy({
            http: http(),
            policy: createPolicy({attributes: ['status', 'skills']}),
            state: {
                status: {value: 'done'},
                skills: {value: [{pk: 1, __str__: 'Grappling'}]},
            },
            metadata: createMetadata({
                fields: {
                    status: {type: 'CharField', choices: [['done', 'Done'], ['new', 'New']]},
                    skills: {
                        type: 'ManyToManyField',
                        choice_model_path: 'Skill',
                        choices: [{pk: 1, __str__: 'Grappling'}, {pk: 2, __str__: 'Climbing'}],
                    },
                },
            }),
        })
        object._loaded = true
        object.$fields.skills.choices = [
            {pk: 1, __str__: 'Grappling'},
            {pk: 2, __str__: 'Climbing'},
        ]

        expect(object.$fields.status.selectedChoice).toEqual(['done', 'Done'])
        expect(object.$fields.status.selectedLabel).toBe('Done')
        expect(object.$fields.skills.selectedPks).toEqual([1])
        expect(object.$fields.skills.selectedChoices).toEqual([])
        expect(object.$fields.skills.add(2).has(2)).toBe(true)
        expect(object.$fields.skills.remove(1).has(1)).toBe(false)
        expect(object.$fields.skills.toggle(2).has(2)).toBe(false)
    })

    test('view GET requests preserve the GET method in the view payload', async () => {
        happyDOM.setURL('http://localhost/')
        let body
        globalThis.Glue = {loadManifests: () => {}}
        const view = new GlueView({
            _config: {glueViewUrlPath: '/view/'},
            sendRequest: async (_url, options) => {
                body = JSON.parse(options.body)
                return {data: {html: ''}}
            },
        }, '/partial/')

        await view.get({page: 2})

        expect(body.method).toBe('GET')
        expect(body.view_payload).toEqual({page: 2})
    })
})
