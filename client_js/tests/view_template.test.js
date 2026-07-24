import {describe, expect, test} from "bun:test"
import GlueConfig from "../src/config"
import GlueHttp from "../src/http"
import GlueView from "../src/view"
import GlueTemplateProxy from "../src/proxies/template"
import {createMetadata, createPolicy, createState} from "./testUtils"

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
                return {data: {html: '<p>Loaded</p>', manifest_list: [{policy: {name: 'new'}}]}}
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

    test('template proxies render and replace HTML targets', async () => {
        global.fetch = async () => new Response(JSON.stringify({
            result: {html: '<p>Rendered</p>'},
            state: createState(),
            policy: createPolicy({attributes: ['render_html']}),
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
})
