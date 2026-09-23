import {describe, expect, test} from "bun:test"
import GlueClient from "../src/client"
import {attributeResponse, createEntry, createPolicyToken} from "./testUtils"

describe('GlueClient registry', () => {
    test('registers named and direct proxies from addressed entries', () => {
        const named = createEntry()
        const direct = createEntry({
            policy: {
                name: 'dashboard',
                namespace: 'dashboard',
                address: 'dashboard#test',
                attributes: [],
                state_snapshot: {},
            },
            staticData: {fields: {}, callables: {}},
        })
        const client = new GlueClient({objects: [named, direct]})

        expect(client.model.gorilla._record.address).toBe('gorilla#test')
        expect(client.dashboard._record.address).toBe('dashboard#test')
        expect(client.model.gorilla).toBe(client.model.gorilla)
    })

    test('rejects an entry whose outer and signed addresses differ', () => {
        const entry = createEntry()
        entry.address = 'wrong#address'
        expect(() => new GlueClient({objects: [entry]})).toThrow('does not match')
    })

    test('reintroducing an address patches the stable proxy', () => {
        const client = new GlueClient({objects: [createEntry()]})
        const held = client.model.gorilla
        client.loadObjects([createEntry({
            policy: {state_snapshot: {id: 1, name: 'Michael', birthday: '1973-03-01'}},
        })])

        expect(client.model.gorilla).toBe(held)
        expect(held.name).toBe('Michael')
    })

    test('binds child paths through the address registry', () => {
        const child = createEntry({
            policy: {
                name: 'parent',
                address: 'gorilla#test.parent',
                state_snapshot: {id: 2, name: 'Matata'},
                attributes: ['id', 'name'],
            },
            staticData: {fields: {
                id: {value_path: 'id', editable: false},
                name: {value_path: 'name', editable: false},
            }, callables: {}},
        })
        const parent = createEntry({
            policy: {children: {parent: child.address}},
            staticData: {children: {parent: {kind: 'model', nullable: true}}},
        })
        const client = new GlueClient({objects: [parent, child]})

        expect(client.model.gorilla.parent).toBe(client._registry.getProxy(child.address))
        expect(client.model.gorilla.parent.$owner).toBe(client.model.gorilla)
    })

    test('keeps function proxies callable and filters declared parameters', async () => {
        const manifest = createEntry({
            policy: {
                name: 'add',
                namespace: 'function',
                address: 'add#test',
                attributes: ['execute'],
                state_snapshot: {},
            },
            staticData: {
                fields: {},
                callables: {execute: {allowed_arguments: ['kwargs']}},
                params: [{name: 'left'}, {name: 'right'}],
            },
        })
        const client = new GlueClient({objects: [manifest]})
        let sent
        client.http.sendAttributeRequest = async request => {
            sent = request
            return attributeResponse('add#test', {result: {result: 12}})
        }

        expect(await client.function.add({left: 5, right: 7, ignored: true})).toBe(12)
        expect(sent.kwargs).toEqual({left: 5, right: 7})
    })

    test('rejects direct and named registrations sharing a namespace', () => {
        const direct = createEntry({policy: {
            name: 'custom', namespace: 'custom', address: 'custom#test', attributes: [], state_snapshot: {},
        }})
        const named = createEntry({policy: {
            name: 'named', namespace: 'custom', address: 'named#test', attributes: [], state_snapshot: {},
        }})
        expect(() => new GlueClient({objects: [direct, named]})).toThrow('already registered directly')
    })

    test('requires addressed entries with a signed token', () => {
        expect(() => new GlueClient({objects: [{
            policy_token: createPolicyToken(),
            state: {},
            metadata: {},
        }]})).toThrow('address and policy_token')
    })

    test('resolves a stamped component through its root address', () => {
        const entry = createEntry({
            policy: {
                name: 'card_123', namespace: 'component', address: 'dashboard#test[card]',
                attributes: ['render'], state_snapshot: {},
            },
            staticData: {fields: {}, callables: {render: {allowed_arguments: []}}},
        })
        const client = new GlueClient({objects: []})
        document.body.innerHTML = '<div data-glue-address="dashboard#test[card]"><span id="inside"></span></div>'
        document.body.firstElementChild.setAttribute('data-glue-objects', JSON.stringify([entry]))

        client.registerComponentsFromDom()

        const proxy = client.from(document.querySelector('#inside'))
        expect(proxy).toBe(client._registry.getProxy(entry.address))
        expect(proxy.$el).toBe(document.body.firstElementChild)
        expect(client.component).toBeUndefined()
    })

    test('a stamped root introduces its children entries', () => {
        const child = createEntry({policy: {name: 'card_form', address: 'card#test.form'}})
        const entry = createEntry({
            policy: {
                name: 'card', namespace: 'component', address: 'card#test',
                attributes: ['form'], state_snapshot: {}, children: {form: child.address},
            },
            staticData: {fields: {}, callables: {}, children: {form: {kind: 'model', nullable: false}}},
        })
        const client = new GlueClient({objects: []})
        document.body.innerHTML = '<div data-glue-address="card#test"></div>'
        document.body.firstElementChild.setAttribute('data-glue-objects', JSON.stringify([entry, child]))

        client.registerComponentsFromDom()

        const proxy = client.from(document.body.firstElementChild)
        expect(proxy.form).toBe(client._registry.getProxy(child.address))
        expect(proxy.form.name).toBe('Koko')
    })

    test('declared events reach source listeners and the component root', () => {
        const entry = createEntry({
            policy: {name: 'card_123', namespace: 'component', address: 'card#test', attributes: []},
            staticData: {fields: {}, callables: {}, events: ['saved']},
        })
        const client = new GlueClient({objects: [entry]})
        document.body.innerHTML = '<div data-glue-address="card#test"></div>'
        const proxy = client.from(document.body.firstElementChild)
        const seen = []
        const stop = proxy.$on('saved', event => seen.push(event.detail.pk))
        document.body.firstElementChild.addEventListener('saved', event => seen.push(event.detail.pk))

        proxy._processEffects({effects: {events: [{name: 'saved', detail: {pk: 7}}]}})
        stop()
        proxy._processEffects({effects: {events: [{name: 'saved', detail: {pk: 8}}]}})

        expect(seen).toEqual([7, 7, 8])
    })
})
