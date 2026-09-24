import {describe, expect, test} from "bun:test"
import GlueClient from "../src/client"
import {attributeResponse, createEntry} from "./testUtils"

function modelClient() {
    const client = new GlueClient({objects: [createEntry({staticData: {events: ['saved']}})]})
    globalThis.Glue = client
    return client
}

describe('proxy lifecycle', () => {
    test('modal exposes its owned form saved event and cleans up on disposal', async () => {
        const form = createEntry({
            policy: {
                name: 'entry_form', namespace: 'form', address: 'modal#test.entry.form',
                attributes: ['save'], state_snapshot: {},
            },
            staticData: {fields: {}, callables: {save: {allowed_arguments: []}}, events: ['saved']},
        })
        const entry = createEntry({
            policy: {
                name: 'entry', namespace: 'model', address: 'modal#test.entry',
                attributes: ['form'], state_snapshot: {}, children: {form: form.address},
            },
            staticData: {
                fields: {}, callables: {}, children: {form: {kind: 'form', nullable: false}},
            },
        })
        const modalEntry = createEntry({
            policy: {
                name: 'entry_modal', namespace: 'component', address: 'modal#test',
                attributes: ['entry'], state_snapshot: {}, children: {entry: entry.address},
            },
            staticData: {
                fields: {}, callables: {}, events: ['saved'],
                children: {entry: {kind: 'model', nullable: false}},
            },
        })
        modalEntry.static_data.forwarded_events = {saved: 'entry.form.saved'}
        const client = new GlueClient({objects: [modalEntry, entry, form]})
        const modal = client._registry.getProxy(modalEntry.address)
        const seen = []
        modal.$on('saved', event => seen.push([event.source, event.currentTarget, event.detail.pk]))
        client.http.sendAttributeRequest = async () => attributeResponse(form.address, {
            result: {success: true},
            effects: {events: [{name: 'saved', detail: {pk: 7}}]},
        })

        await modal.entry.form.save()

        expect(seen).toEqual([[modal.entry.form, modal, 7]])
        modal.$dispose()
        expect(client._registry.getProxy(form.address)).toBeNull()
    })

    test('exposing a mounted child event does not duplicate its bubbling DOM event', async () => {
        const child = createEntry({
            policy: {
                name: 'editor', namespace: 'component', address: 'modal#test.editor',
                attributes: ['save'], state_snapshot: {},
            },
            staticData: {fields: {}, callables: {save: {allowed_arguments: []}}, events: ['saved']},
        })
        const modalEntry = createEntry({
            policy: {
                name: 'entry_modal', namespace: 'component', address: 'modal#test',
                attributes: ['editor'], state_snapshot: {}, children: {editor: child.address},
            },
            staticData: {
                fields: {}, callables: {}, events: ['saved'],
                children: {editor: {kind: 'component', nullable: false}},
            },
        })
        modalEntry.static_data.forwarded_events = {saved: 'editor.saved'}
        const client = new GlueClient({objects: [modalEntry, child]})
        document.body.innerHTML = '<div data-glue-address="modal#test"><div data-glue-address="modal#test.editor"></div></div>'
        const modal = client._registry.getProxy(modalEntry.address)
        const events = []
        modal.$el.addEventListener('saved', event => events.push(event.detail.pk))
        client.http.sendAttributeRequest = async () => attributeResponse(child.address, {
            result: {success: true},
            effects: {events: [{name: 'saved', detail: {pk: 7}}]},
        })

        await modal.editor.save()

        expect(events).toEqual([7])
    })

    test('delivers declared events after the addressed response applies', async () => {
        const client = modelClient()
        const proxy = client.model.gorilla
        const events = []
        proxy.$on('saved', event => events.push([event.source, proxy.name]))
        client.http.sendAttributeRequest = async () => attributeResponse('gorilla#test', {
            result: {ok: true},
            computed_data: {name: 'Updated'},
            effects: {events: [{name: 'saved', detail: {pk: 1}}]},
        })

        await proxy.save()

        expect(events).toEqual([[proxy, 'Updated']])
    })

    test('removes registered listeners', async () => {
        const client = modelClient()
        const proxy = client.model.gorilla
        let calls = 0
        const listener = () => calls++
        const stop = proxy.$on('saved', listener)
        stop()
        client.http.sendAttributeRequest = async () => attributeResponse('gorilla#test', {
            result: null,
            effects: {events: [{name: 'saved', detail: {}}]},
        })

        await proxy.save()

        expect(calls).toBe(0)
    })

    test('a rejected event listener reports its error without changing the save result', async () => {
        const client = modelClient()
        const proxy = client.model.gorilla
        const errors = []
        client.onError(({error}) => errors.push(error.message))
        proxy.$on('saved', async () => {
            throw new Error('refresh failed')
        })
        client.http.sendAttributeRequest = async () => attributeResponse('gorilla#test', {
            result: {success: true},
            effects: {events: [{name: 'saved', detail: {}}]},
        })

        expect(await proxy.save()).toEqual({success: true})
        await Promise.resolve()
        expect(errors).toEqual(['refresh failed'])
    })

    test('routes messages through a proxy handler before the global handler', async () => {
        const client = modelClient()
        const proxy = client.model.gorilla
        const local = []
        const global = []
        client.onMessage(event => global.push(event))
        proxy.onMessage(event => local.push(event))
        client.http.sendAttributeRequest = async () => attributeResponse('gorilla#test', {
            result: null,
            effects: {messages: [{level: 'success', message: 'Saved'}]},
        })

        await proxy.save()

        expect(local).toHaveLength(1)
        expect(local[0].proxy).toBe(proxy)
        expect(global).toEqual([])
    })

    test('does not deliver events when an operation fails', async () => {
        const client = modelClient()
        const proxy = client.model.gorilla
        const events = []
        proxy.$on('saved', event => events.push(event))
        client.http.sendAttributeRequest = async () => {
            throw new Error('offline')
        }

        await expect(proxy.save()).rejects.toThrow('offline')
        expect(events).toHaveLength(0)
    })

    test('does not treat untagged result objects as manifests', async () => {
        const client = modelClient()
        const result = {address: 'other#test', policy_token: 'not-a-token', value: 3}
        client.http.sendAttributeRequest = async () => attributeResponse('gorilla#test', {result})

        expect(await client.model.gorilla.save()).toEqual(result)
        expect(client._registry.getProxy('other#test')).toBeNull()
    })
})
