import {describe, expect, test} from "bun:test"
import GlueClient from "../src/client"
import GlueView from "../src/view"
import {htmlResultFromResponse} from "../src/htmlRenderer"
import {attributeResponse, createEntry} from "./testUtils"

describe('view and template facades', () => {
    test('a GET view requests the real same-origin URL with the payload as query parameters', async () => {
        happyDOM.setURL('http://localhost/')
        const requests = []
        const loaded = []
        const previousGlue = globalThis.Glue
        globalThis.Glue = {loadObjects: objects => loaded.push(...objects)}
        const child = createEntry({policy: {name: 'child', address: 'child#test'}})
        const view = new GlueView({
            _config: {glueViewMediaType: 'application/vnd.django-glue.view+json'},
            sendRequest: async (url, options) => {
                requests.push({url, options})
                return {data: {is_glue_template_response: true, html: '<p>Loaded</p>', objects: [child]}}
            },
        }, 'http://example.com/detail/?tab=1', {shared: true})

        try {
            expect(await view.get({local: 1})).toBe('<p>Loaded</p>')
        } finally {
            globalThis.Glue = previousGlue
        }
        expect(requests[0].url).toBe('/detail/?tab=1&shared=true&local=1')
        expect(requests[0].options.method).toBe('GET')
        expect(requests[0].options.headers.Accept).toBe('application/vnd.django-glue.view+json')
        expect(loaded).toEqual([child])
    })

    test('a POST view sends the merged payload as CSRF-protected JSON to the real URL', async () => {
        happyDOM.setURL('http://localhost/')
        let request
        const view = new GlueView({
            _config: {glueViewMediaType: 'application/vnd.django-glue.view+json'},
            sendRequest: async (url, options) => {
                request = {url, options}
                return {data: {is_glue_template_response: true, html: '<p>Posted</p>', objects: []}}
            },
        }, '/detail/', {shared: true})

        expect(await view.post({local: 1})).toBe('<p>Posted</p>')
        expect(request.url).toBe('/detail/')
        expect(request.options.csrfProtected).toBeTrue()
        expect(JSON.parse(request.options.body)).toEqual({shared: true, local: 1})
    })

    test('a response without the envelope marker is a non-fragment outcome', async () => {
        happyDOM.setURL('http://localhost/')
        const view = new GlueView({
            _config: {glueViewMediaType: 'application/vnd.django-glue.view+json'},
            sendRequest: async () => ({data: null}),
        }, '/download/')
        document.body.innerHTML = '<div id="target"><b>Kept</b></div>'

        expect(await view.renderInnerHtml('#target')).toBeNull()
        expect(document.querySelector('#target').innerHTML).toBe('<b>Kept</b>')
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

    test('callable template responses load their public objects', async () => {
        const source = createEntry({
            policy: {attributes: ['save'], state_snapshot: {}},
            staticData: {callables: {save: {allowed_arguments: []}}},
        })
        const child = createEntry({policy: {
            name: 'new_row', address: 'new-row#test', state_snapshot: {id: 7, name: 'New'},
        }})
        const client = new GlueClient({objects: [source]})
        globalThis.Glue = client
        client.http.sendAttributeRequest = async () => ({data: {objects: [
            {address: 'gorilla#test', html: '<p>Row list</p>', result: null},
            child,
        ]}})

        const result = await client.model.gorilla.save()

        expect(String(result)).toBe('<p>Row list</p>')
        expect(client.model.new_row).toBe(client._registry.getProxy(child.address))
    })
})
