import {describe, expect, test} from "bun:test"
import GlueClient from "../src/client"
import GlueView from "../src/view"
import {htmlResultFromResponse} from "../src/htmlRenderer"
import {createManifest} from "./testUtils"

describe('view and template facades', () => {
    test('view requests merge payloads, preserve the inner method, and load manifests', async () => {
        happyDOM.setURL('http://localhost/')
        let request
        const loaded = []
        const previousGlue = globalThis.Glue
        globalThis.Glue = {loadManifests: manifests => loaded.push(...manifests)}
        const child = createManifest({policy: {name: 'child', address: 'child#test'}})
        const view = new GlueView({
            _config: {glueViewUrlPath: '/view/'},
            sendRequest: async (_url, options) => {
                request = JSON.parse(options.body)
                return {data: {html: '<p>Loaded</p>', manifest_list: [child]}}
            },
        }, 'http://example.com/detail/', {shared: true})

        try {
            expect(await view.get({local: 1})).toBe('<p>Loaded</p>')
        } finally {
            globalThis.Glue = previousGlue
        }
        expect(request).toEqual({
            url_path: '/detail/', method: 'GET', view_payload: {shared: true, local: 1},
        })
        expect(loaded).toEqual([child])
    })

    test('inserts returned HTML at each adjacent position', async () => {
        let html = '<span>Before</span>'
        const result = htmlResultFromResponse({html})
        document.body.innerHTML = '<div id="target"><b>Old</b></div>'

        await result.renderInsertAdjacentHtmlBeforeBegin('#target')
        result.html = '<i>First</i>'
        await result.renderInsertAdjacentHtmlAfterBegin('#target')
        result.html = '<i>Last</i>'
        await result.renderInsertAdjacentHtmlBeforeEnd('#target')
        result.html = '<span>After</span>'
        await result.renderInsertAdjacentHtmlAfterEnd('#target')

        expect(document.body.innerHTML).toBe(
            '<span>Before</span><div id="target"><i>First</i><b>Old</b><i>Last</i></div><span>After</span>'
        )
    })

    test('rejects an invalid adjacent position', async () => {
        document.body.innerHTML = '<div id="target"></div>'
        const result = htmlResultFromResponse({html: '<p>New</p>'})

        await expect(result._renderInsertAdjacentHtml('#target', 'middle')).rejects.toThrow(
            'Invalid insert position: middle'
        )
    })

    test('template proxies render through the shared HTML interface', async () => {
        const manifest = createManifest({
            policy: {
                name: 'card', namespace: 'template', address: 'card#test',
                attributes: ['render_html'], state_snapshot: {},
            },
            staticData: {fields: {}, callables: {render_html: {allowed_arguments: ['title']}}},
        })
        const client = new GlueClient({manifest_list: [manifest]})
        client.http.sendAttributeRequest = async request => {
            expect(request.kwargs).toEqual({title: 'Profile'})
            return {data: {result: {html: '<p>Rendered</p>'}}}
        }
        document.body.innerHTML = '<div id="target"></div>'

        await client.template.card.renderInnerHtml('#target', {title: 'Profile'})

        expect(document.querySelector('#target').innerHTML).toBe('<p>Rendered</p>')
    })

    test('callable template responses load their public manifests', async () => {
        const source = createManifest({
            policy: {attributes: ['save'], state_snapshot: {}},
            staticData: {callables: {save: {allowed_arguments: []}}},
        })
        const child = createManifest({policy: {
            name: 'new_row', address: 'new-row#test', state_snapshot: {id: 7, name: 'New'},
        }})
        const client = new GlueClient({manifest_list: [source]})
        globalThis.Glue = client
        client.http.sendAttributeRequest = async () => ({data: {result: {
            is_glue_template_response: true,
            html: '<p>Row list</p>',
            manifest_list: [child],
        }}})

        const result = await client.model.gorilla.save()

        expect(String(result)).toBe('<p>Row list</p>')
        expect(client.model.new_row).toBe(client._registry.getProxy(child.address))
    })
})
