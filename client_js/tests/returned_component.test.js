import {describe, expect, test} from "bun:test"
import GlueClient from "../src/client"
import {createEntry} from "./testUtils"

const MODAL_ADDRESS = 'dashboard#test["tdeadbeefcafe1234"]'

const dashboardPolicy = {
    name: 'dashboard', namespace: 'component', address: 'dashboard#test',
    attributes: ['open_modal', 'render'], state_snapshot: {},
}

function modalEntry(fields = {}) {
    return createEntry({
        policy: {
            name: 'modal', namespace: 'component', address: MODAL_ADDRESS,
            attributes: ['render', 'touch'], state_snapshot: {},
        },
        staticData: {
            value_attributes: {},
            callables: {render: {allowed_arguments: []}, touch: {allowed_arguments: []}},
        },
        ...fields,
    })
}

// What a render() call on the modal is answered with: its markup, stamped as
// Component.render() stamps its root.
function renderAnswer(text) {
    return {
        address: MODAL_ADDRESS,
        result: null,
        html: `<div data-glue-address='${MODAL_ADDRESS}'>${text}</div>`,
        effects: {messages: []},
    }
}

function dashboardClient(modalFields) {
    const client = new GlueClient({objects: [
        createEntry({
            policy: dashboardPolicy,
            staticData: {
                value_attributes: {},
                callables: {open_modal: {allowed_arguments: [], returns_glue: true}},
            },
        }),
    ]})
    globalThis.Glue = client
    const requests = []
    client.http.sendAttributeRequest = async request => {
        requests.push(request)
        if (request.attribute === 'open_modal') {
            return {data: {objects: [
                {address: 'dashboard#test', result: MODAL_ADDRESS, effects: {messages: []}},
                modalEntry(modalFields),
            ]}}
        }
        if (request.attribute === 'render') return {data: {objects: [renderAnswer('Rendered by request')]}}
        return {data: {objects: [{address: MODAL_ADDRESS, result: null, effects: {messages: []}}]}}
    }
    document.body.innerHTML = '<div id="modal-content"></div>'
    return {client, dashboard: client._registry.getProxy('dashboard#test'), requests}
}

describe('a returned component that arrives rendered (ADR 043)', () => {
    test('renders from the answer it arrived with, without a request', async () => {
        const {dashboard, requests} = dashboardClient({answers: {render: renderAnswer('Arrived rendered')}})

        const modal = await dashboard.open_modal()
        await modal.renderInnerHtml('#modal-content')

        expect(requests.map(request => request.attribute)).toEqual(['open_modal'])
        expect(document.querySelector('#modal-content').textContent).toBe('Arrived rendered')
        expect(modal.$el).toBe(document.querySelector(`[data-glue-address='${MODAL_ADDRESS}']`))
    })

    test('answers a direct render() with its HTML', async () => {
        const {dashboard, requests} = dashboardClient({answers: {render: renderAnswer('Arrived rendered')}})

        const modal = await dashboard.open_modal()
        const rendered = await modal.render()

        expect(requests.map(request => request.attribute)).toEqual(['open_modal'])
        expect(rendered.html).toContain('Arrived rendered')
    })

    test('uses the answer once; the next render is a request', async () => {
        const {dashboard, requests} = dashboardClient({answers: {render: renderAnswer('Arrived rendered')}})

        const modal = await dashboard.open_modal()
        await modal.renderInnerHtml('#modal-content')
        await modal.renderInnerHtml('#modal-content')

        expect(requests.map(request => request.attribute)).toEqual(['open_modal', 'render'])
        expect(document.querySelector('#modal-content').textContent).toBe('Rendered by request')
    })

    test('drops the answer once another call has changed the component', async () => {
        const {dashboard, requests} = dashboardClient({answers: {render: renderAnswer('Arrived rendered')}})

        const modal = await dashboard.open_modal()
        await modal.touch()
        await modal.renderInnerHtml('#modal-content')

        expect(requests.map(request => request.attribute)).toEqual(['open_modal', 'touch', 'render'])
        expect(document.querySelector('#modal-content').textContent).toBe('Rendered by request')
    })

    test('a render with arguments is a request', async () => {
        const {dashboard, requests} = dashboardClient({answers: {render: renderAnswer('Arrived rendered')}})

        const modal = await dashboard.open_modal()
        await modal.renderInnerHtml('#modal-content', {variant: 'compact'})

        expect(requests.map(request => request.attribute)).toEqual(['open_modal', 'render'])
    })

    test('a component that arrives without an answer renders by request', async () => {
        const {dashboard, requests} = dashboardClient()

        const modal = await dashboard.open_modal()
        await modal.renderInnerHtml('#modal-content')

        expect(requests.map(request => request.attribute)).toEqual(['open_modal', 'render'])
        expect(document.querySelector('#modal-content').textContent).toBe('Rendered by request')
    })
})
