import {describe, expect, test} from "bun:test"
import GlueConfig from "../src/config"
import GlueClient from "../src/client"
import GlueHttp from "../src/http"
import GlueView from "../src/view"
import GlueHtmlResult from "../src/htmlResult"
import GlueTemplateProxy from "../src/proxies/template"
import {createMetadata, createPolicy, createPolicyToken, createState, mockOperationFetch} from "./testUtils"

describe('Glue views and template proxies', () => {
    test('GlueView merges payloads, loads manifests, and returns HTML', async () => {
        happyDOM.setURL('http://localhost/')
        let request
        const manifests = []
        globalThis.Glue = {loadManifests: value => manifests.push(...value)}
        const http = {
            _config: {glueViewUrlPath: '/__dg__/glue_view/'},
            sendRequest: async (_url, options) => {
                request = JSON.parse(options.body)
                return {data: {html: '<p>Loaded</p>', manifest_list: [{
                    is_glue_manifest: true,
                    policy_token: createPolicyToken({name: 'new'}),
                }]}}
            },
        }
        const view = new GlueView(http, 'http://example.com/task/detail/', {shared: true})

        expect(await view.post({local: 1})).toBe('<p>Loaded</p>')
        expect(request).toEqual({
            url_path: '/task/detail/',
            method: 'POST',
            view_payload: {shared: true, local: 1},
        })
        expect(manifests).toHaveLength(1)
    })

    test('GlueView replaces inner and outer HTML targets', async () => {
        happyDOM.setURL('http://localhost/')
        const http = {
            _config: {glueViewUrlPath: '/view/'},
            sendRequest: async () => ({data: {html: '<span>New</span>', manifest_list: []}}),
        }
        const view = new GlueView(http, '/partial/')
        document.body.innerHTML = '<div id="inner"><b>Old</b></div><div id="outer"><b>Old</b></div>'

        await view.renderInnerHtml('#inner')
        expect(document.querySelector('#inner').innerHTML).toBe('<span>New</span>')
        await view.renderOuterHtml('#outer')
        expect(document.querySelector('#outer')).toBeNull()
        expect(document.body.innerHTML).toContain('<span>New</span>')
    })

    test('GlueView inserts HTML adjacent to targets', async () => {
        happyDOM.setURL('http://localhost/')
        let html = '<span>New</span>'
        const http = {
            _config: {glueViewUrlPath: '/view/'},
            sendRequest: async () => ({data: {html, manifest_list: []}}),
        }
        const view = new GlueView(http, '/partial/')
        document.body.innerHTML = '<div id="target"><b>Old</b></div>'

        await view.renderInsertAdjacentHtmlBeforeBegin('#target')
        expect(document.body.innerHTML).toBe('<span>New</span><div id="target"><b>Old</b></div>')

        html = '<i>First</i>'
        await view.renderInsertAdjacentHtmlAfterBegin('#target')
        expect(document.querySelector('#target').innerHTML).toBe('<i>First</i><b>Old</b>')

        html = '<i>Last</i>'
        await view.renderInsertAdjacentHtmlBeforeEnd('#target')
        expect(document.querySelector('#target').innerHTML).toBe('<i>First</i><b>Old</b><i>Last</i>')

        html = '<em>After</em>'
        const result = await view.renderInsertAdjacentHtmlAfterEnd('#target')
        expect(result).toBe('<em>After</em>')
        expect(document.body.innerHTML).toContain('<div id="target"><i>First</i><b>Old</b><i>Last</i></div><em>After</em>')
    })

    test('GlueView rejects an invalid insert position', async () => {
        happyDOM.setURL('http://localhost/')
        const http = {
            _config: {glueViewUrlPath: '/view/'},
            sendRequest: async () => ({data: {html: '<span>New</span>', manifest_list: []}}),
        }
        const view = new GlueView(http, '/partial/')
        document.body.innerHTML = '<div id="target"></div>'

        await expect(view._renderInsertAdjacentHtml('#target', 'nowhere')).rejects.toThrow('Invalid insert position: nowhere')
    })

    test('template proxies render and replace HTML targets', async () => {
        global.fetch = async () => new Response(JSON.stringify({
            result: {html: '<p>Rendered</p>'},
            state: createState(),
            policy_token: createPolicyToken({attributes: ['render_html']}),
            metadata: createMetadata({attributes: {render_html: {namespace: 'callable'}}}),
        }), {status: 200, headers: {'Content-Type': 'application/json'}})
        const proxy = new GlueTemplateProxy({
            http: new GlueHttp(new GlueConfig()),
            policy: createPolicy({name: 'card', namespace: 'template', attributes: ['render_html']}),
            state: {},
            metadata: createMetadata({attributes: {render_html: {namespace: 'callable'}}}),
        })
        document.body.innerHTML = '<div id="inner"><b>Old</b></div><div id="outer"><b>Old</b></div>'

        expect(await proxy.renderHtml()).toBe('<p>Rendered</p>')
        await proxy.renderInnerHtml('#inner')
        expect(document.querySelector('#inner').innerHTML).toBe('<p>Rendered</p>')
        await proxy.renderOuterHtml('#outer')
        expect(document.querySelector('#outer')).toBeNull()
    })

    test('template proxies insert HTML adjacent to targets', async () => {
        let html = '<span>New</span>'
        global.fetch = async () => new Response(JSON.stringify({
            result: {html},
            state: createState(),
            policy_token: createPolicyToken({attributes: ['render_html']}),
            metadata: createMetadata({attributes: {render_html: {namespace: 'callable'}}}),
        }), {status: 200, headers: {'Content-Type': 'application/json'}})
        const proxy = new GlueTemplateProxy({
            http: new GlueHttp(new GlueConfig()),
            policy: createPolicy({name: 'card', namespace: 'template', attributes: ['render_html']}),
            state: {},
            metadata: createMetadata({attributes: {render_html: {namespace: 'callable'}}}),
        })
        document.body.innerHTML = '<div id="target"><b>Old</b></div>'

        await proxy.renderInsertAdjacentHtmlBeforeBegin('#target')
        expect(document.body.innerHTML).toBe('<span>New</span><div id="target"><b>Old</b></div>')

        html = '<i>First</i>'
        await proxy.renderInsertAdjacentHtmlAfterBegin('#target')
        expect(document.querySelector('#target').innerHTML).toBe('<i>First</i><b>Old</b>')

        html = '<i>Last</i>'
        await proxy.renderInsertAdjacentHtmlBeforeEnd('#target')
        expect(document.querySelector('#target').innerHTML).toBe('<i>First</i><b>Old</b><i>Last</i>')

        html = '<em>After</em>'
        const result = await proxy.renderInsertAdjacentHtmlAfterEnd('#target')
        expect(result).toBe('<em>After</em>')
        expect(document.body.innerHTML).toContain('<div id="target"><i>First</i><b>Old</b><i>Last</i></div><em>After</em>')
    })

    test('a @Glue.attr call returning a GlueTemplateResponse resolves to a GlueHtmlResult', async () => {
        happyDOM.setURL('http://localhost/')
        const calls = mockOperationFetch({
            result: {
                is_glue_template_response: true,
                html: '<p>Row list</p>',
                manifest_list: [{
                    is_glue_manifest: true,
                    policy_token: createPolicyToken({name: 'new_row', namespace: 'model', attributes: ['id']}),
                    state: {id: {value: 7}},
                    metadata: createMetadata(),
                }],
            },
            policy_token: createPolicyToken({name: 'gorillas', namespace: 'querySet', attributes: ['some_custom_thing']}),
            metadata: createMetadata({namespace: 'querySet', attributes: {some_custom_thing: {namespace: 'callable'}}}),
        })
        const client = new GlueClient({
            manifest_list: [{
                is_glue_manifest: true,
                policy_token: createPolicyToken({name: 'gorillas', namespace: 'querySet', attributes: ['some_custom_thing']}),
                state: {},
                metadata: createMetadata({namespace: 'querySet', attributes: {some_custom_thing: {namespace: 'callable'}}}),
            }],
        })
        document.body.innerHTML = '<div id="target"><b>Old</b></div>'

        const result = await client.querySet.gorillas.some_custom_thing()

        expect(calls).toHaveLength(1)
        expect(result).toBeInstanceOf(GlueHtmlResult)
        expect(result.html).toBe('<p>Row list</p>')
        expect(result.toString()).toBe('<p>Row list</p>')

        await result.renderInnerHtml('#target')
        expect(document.querySelector('#target').innerHTML).toBe('<p>Row list</p>')

        // The manifest riding along in the result loaded onto the client,
        // same as Glue.view's manifest_list -- a proxy for it is reachable
        // without a separate round trip.
        expect(client.model.new_row).toBeInstanceOf(Object)
    })
})
