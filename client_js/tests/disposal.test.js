import {describe, expect, test} from "bun:test"
import GlueClient from "../src/client"
import {createEntry, createPolicyToken, createStaticData} from "./testUtils"

const rootPolicy = {
    name: 'root', namespace: 'root', address: 'root#test',
    attributes: ['save'], children: {form: 'form#test'}, state_snapshot: {},
}
const formPolicy = {
    name: 'form', namespace: 'form', address: 'form#test',
    attributes: ['validate'], children: {nested: 'nested#test'}, state_snapshot: {name: 'Ada'},
}
const nestedPolicy = {
    name: 'nested', namespace: 'model', address: 'nested#test',
    state_snapshot: {note: 'hi'},
}

function formEntry(address = 'form#test') {
    return createEntry({
        policy: {...formPolicy, address},
        staticData: {
            children: {nested: {kind: 'model', nullable: true}},
            callables: {validate: {allowed_arguments: []}},
        },
    })
}

function tree() {
    const client = new GlueClient({objects: [
        createEntry({
            policy: rootPolicy,
            staticData: {children: {form: {kind: 'form', nullable: false}}},
        }),
        formEntry(),
        createEntry({policy: nestedPolicy}),
    ]})
    globalThis.Glue = client
    const root = client.root
    return {client, root, form: root.form, nested: root.form.nested}
}

function gatedHttp(client, {onValidate, onRoot}) {
    let gateResolve
    const gate = new Promise(resolve => {gateResolve = resolve})
    client.http.sendAttributeRequest = async (params) => {
        if (params.attribute === 'validate') {
            await gate
            return onValidate(params)
        }
        return onRoot(params)
    }
    return {gate, release: () => gateResolve()}
}

describe('replacement and removal disposal', () => {
    test('the same path with the same address preserves proxy, draft, and queue', async () => {
        const {client, root, form, nested} = tree()
        const {release} = gatedHttp(client, {
            onValidate: () => ({data: {objects: [{address: 'form#test', result: {valid: true}}]}}),
            onRoot: () => ({data: {objects: [{address: 'root#test', result: {saved: true}}]}}),
        })

        form.name = 'Draft'
        const validatePromise = form.validate()
        const result = await root.save()

        expect(result).toEqual({saved: true})
        expect(root.form).toBe(form)
        expect(root.form.nested).toBe(nested)
        expect(form.name).toBe('Draft')
        release()
        expect(await validatePromise).toEqual({valid: true})
    })

    test('a different address at a path is a replacement that disposes the old child', async () => {
        const {client, root, form} = tree()
        const replacementPolicy = createPolicyToken({
            ...rootPolicy,
            children: {form: 'form#other'},
            created_at: 2,
        })
        client.http.sendAttributeRequest = async (params) => ({data: {objects: [
            {address: 'root#test', policy_token: replacementPolicy, result: {}},
            formEntry('form#other'),
        ]}})

        const oldForm = form
        const nested = form.nested
        await root.save()

        expect(root.form).not.toBe(oldForm)
        expect(root.form._record.address).toBe('form#other')
        expect(client._registry.getRecord('form#test')).toBeUndefined()
        expect(oldForm._record.disposed).toBe(true)
        expect(root.form.nested).toBe(nested)
        expect(nested._record.owner).toEqual({address: 'form#other', path: 'nested'})
        expect(nested._record.disposed).toBe(false)

        let error
        try {
            await oldForm.validate()
        } catch (e) {
            error = e
        }
        expect(error.code).toBe('disposed')
    })

    test('an absent nullable path is a removal', async () => {
        const {client, root, form, nested} = tree()
        const emptyChildrenToken = createPolicyToken({
            ...formPolicy,
            children: {},
            created_at: 2,
        })
        client.http.sendAttributeRequest = async (params) => {
            if (params.attribute === 'validate') {
                return {data: {objects: [
                    {address: 'form#test', policy_token: emptyChildrenToken, result: {valid: true}},
                ]}}
            }
            return {data: {objects: [{address: 'root#test', result: {}}]}}
        }

        await form.validate()

        expect(form.nested).toBeNull()
        expect(client._registry.getRecord('nested#test')).toBeUndefined()
        expect(nested._record.disposed).toBe(true)
        expect(client._registry.getRecord('form#test')).toBeDefined()
        expect(root.form).toBe(form)
    })

    test('disposing the root recursively tears down the owned tree', () => {
        const {client, root, form, nested} = tree()

        root.$dispose()

        expect(client._registry.getRecord('root#test')).toBeUndefined()
        expect(client._registry.getRecord('form#test')).toBeUndefined()
        expect(client._registry.getRecord('nested#test')).toBeUndefined()
        expect(root._record.disposed).toBe(true)
        expect(form._record.disposed).toBe(true)
        expect(nested._record.disposed).toBe(true)
        expect(client.root).toBeNull()
    })

    test('a slot-bound child refuses client-side disposal', () => {
        const {client, form} = tree()

        expect(() => form.$dispose()).toThrow('bound to its owner at path "form"')
        expect(client._registry.getRecord('form#test')).toBeDefined()
    })

    test('effects.dispose disposes an owned address without a children map change', async () => {
        const {client, root, form, nested} = tree()
        client.http.sendAttributeRequest = async (params) => ({data: {objects: [
            {
                address: 'root#test',
                result: {},
                effects: {messages: [], dispose: ['form#test']},
            },
        ]}})

        await root.save()

        expect(client._registry.getRecord('form#test')).toBeUndefined()
        expect(client._registry.getRecord('nested#test')).toBeUndefined()
        expect(form._record.disposed).toBe(true)
        expect(nested._record.disposed).toBe(true)
        expect(client._registry.getRecord('root#test')).toBeDefined()
        expect(root._record.disposed).toBe(false)
    })
})

describe('transient callable results', () => {
    const dashboardPolicy = {
        name: 'dashboard', namespace: 'dashboard', address: 'dashboard#test',
        attributes: ['spawn'], state_snapshot: {},
    }

    function dashboardClient() {
        const client = new GlueClient({objects: [
            createEntry({
                policy: dashboardPolicy,
                staticData: {
                    callables: {spawn: {allowed_arguments: [], returns_glue: true}},
                },
            }),
        ]})
        globalThis.Glue = client
        return {client, dashboard: client.dashboard}
    }

    function spawnResponse(address, note) {
        return {data: {objects: [
            {
                address: 'dashboard#test',
                result: address,
                effects: {messages: []},
            },
            createEntry({
                policy: {
                    name: 'spawned', namespace: 'model', address,
                    state_snapshot: {note},
                },
                staticData: {callables: {validate: {allowed_arguments: []}}},
            }),
        ]}}
    }

    test('a Glue result is registered with the producer as its lifecycle owner', async () => {
        const {client, dashboard} = dashboardClient()
        const address = 'dashboard#test["tdeadbeefcafe1234"]'
        client.http.sendAttributeRequest = async () => spawnResponse(address, 'first')

        const result = await dashboard.spawn()

        expect(result).not.toBe(address)
        expect(result._record.address).toBe(address)
        expect(result._record.owner).toEqual({address: 'dashboard#test', path: null})
    })

    test('repeated spawns mint distinct live addresses', async () => {
        const {client, dashboard} = dashboardClient()
        let call = 0
        client.http.sendAttributeRequest = async () => {
            call += 1
            return spawnResponse(`dashboard#test["t${'0'.repeat(14)}${call}"]`, `note ${call}`)
        }

        const first = await dashboard.spawn()
        const second = await dashboard.spawn()

        expect(first._record.address).not.toBe(second._record.address)
        expect(client._registry.getRecord(first._record.address)).toBeDefined()
        expect(client._registry.getRecord(second._record.address)).toBeDefined()
    })

    test('$dispose tears down a transient result and only it', async () => {
        const {client, dashboard} = dashboardClient()
        let call = 0
        client.http.sendAttributeRequest = async () => {
            call += 1
            return spawnResponse(`dashboard#test["t${'0'.repeat(14)}${call}"]`, `note ${call}`)
        }

        const first = await dashboard.spawn()
        const second = await dashboard.spawn()
        first.$dispose()

        expect(client._registry.getRecord(first._record.address)).toBeUndefined()
        expect(first._record.disposed).toBe(true)
        expect(client._registry.getRecord(second._record.address)).toBeDefined()
        expect(dashboard._record.disposed).toBe(false)
    })

    test('disposing the producer cascades to its transient results', async () => {
        const {client, dashboard} = dashboardClient()
        let call = 0
        client.http.sendAttributeRequest = async () => {
            call += 1
            return spawnResponse(`dashboard#test["t${'0'.repeat(14)}${call}"]`, `note ${call}`)
        }

        const first = await dashboard.spawn()
        const second = await dashboard.spawn()
        dashboard.$dispose()

        expect(client._registry.getRecord(first._record.address)).toBeUndefined()
        expect(client._registry.getRecord(second._record.address)).toBeUndefined()
        expect(first._record.disposed).toBe(true)
        expect(second._record.disposed).toBe(true)
        expect(dashboard._record.disposed).toBe(true)
    })

    test('an expired transient result names its producer instead of a repair', async () => {
        const {client, dashboard} = dashboardClient()
        const address = 'dashboard#test["tdeadbeefcafe1234"]'
        client.http.sendAttributeRequest = async (params) => {
            if (params.attribute === 'validate') {
                return {data: {objects: [{
                    address,
                    error: {code: 'policy_expired', message: 'policy expired'},
                }]}}
            }
            return spawnResponse(address, 'first')
        }
        const result = await dashboard.spawn()

        let error
        try {
            await result.validate()
        } catch (e) {
            error = e
        }
        expect(error.code).toBe('policy_expired')
        expect(error.owner).toEqual({name: 'dashboard', address: 'dashboard#test'})
        expect(result._record.stale).toBe(true)

        let staleError
        try {
            await result.validate()
        } catch (e) {
            staleError = e
        }
        expect(staleError.code).toBe('policy_expired')
        expect(staleError.message).toContain('re-run the call that produced it')
    })
})

describe('late responses for disposed generations', () => {
    test('an in-flight call survives an owner refresh that re-introduces its entry', async () => {
        const {client, root, form} = tree()
        let gateResolve
        const gate = new Promise(resolve => {gateResolve = resolve})
        const changedMapToken = createPolicyToken({
            ...rootPolicy,
            children: {form: 'form#test', extra: 'extra#test'},
            created_at: 2,
        })
        client.http.sendAttributeRequest = async (params) => {
            if (params.attribute === 'validate') {
                await gate
                return {data: {objects: [{address: 'form#test', result: {valid: true}}]}}
            }
            return {data: {objects: [
                {address: 'root#test', policy_token: changedMapToken, result: {}},
                formEntry(),
                createEntry({policy: {name: 'extra', namespace: 'model', address: 'extra#test'}}),
            ]}}
        }

        const validatePromise = form.validate()
        await root.save()
        gateResolve()
        expect(await validatePromise).toEqual({valid: true})
        expect(root.form).toBe(form)
    })

    test('reintroducing a disposed address creates a new proxy and discards the old response', async () => {
        const {client, root, form} = tree()
        let gateResolve
        const gate = new Promise(resolve => {gateResolve = resolve})
        let step = 0
        client.http.sendAttributeRequest = async (params) => {
            if (params.attribute === 'validate') {
                await gate
                return {data: {objects: [{address: 'form#test', result: {valid: true}}]}}
            }
            step += 1
            if (step === 1) {
                return {data: {objects: [
                    {address: 'root#test', policy_token: createPolicyToken({...rootPolicy, children: {}, created_at: 2}), result: {}},
                ]}}
            }
            return {data: {objects: [
                {address: 'root#test', policy_token: createPolicyToken({...rootPolicy, children: {form: 'form#test'}, created_at: 3}), result: {}},
                formEntry(),
            ]}}
        }

        const validatePromise = form.validate()
        const oldForm = root.form
        await root.save()
        expect(root.form).toBeNull()
        expect(oldForm._record.disposed).toBe(true)
        await root.save()
        expect(root.form).not.toBe(oldForm)
        expect(root.form._record.disposed).toBe(false)
        expect(oldForm._record.disposed).toBe(true)
        gateResolve()
        expect(await validatePromise).toBeUndefined()
        let tombstoneError
        try {
            await oldForm.validate()
        } catch (error) {
            tombstoneError = error
        }
        expect(tombstoneError.code).toBe('disposed')
    })

    test('queued calls reject against the tombstone after disposal', async () => {
        const {client, root, form} = tree()
        let gateResolve
        const gate = new Promise(resolve => {gateResolve = resolve})
        client.http.sendAttributeRequest = async (params) => {
            if (params.attribute === 'validate') {
                await gate
                return {data: {objects: [{address: 'form#test', result: {valid: true}}]}}
            }
            return {data: {objects: [{address: 'root#test', result: {}}]}}
        }

        const validatePromise = form.validate()
        await new Promise(resolve => setTimeout(resolve, 0))
        root.$dispose()
        let queuedError
        try {
            await form.validate()
        } catch (e) {
            queuedError = e
        }
        expect(queuedError.code).toBe('disposed')

        gateResolve()
        expect(await validatePromise).toBeUndefined()
        expect(client._registry.getRecord('form#test')).toBeUndefined()
    })
})

describe('effects channel', () => {
    test('effects.redirect navigates the browser', async () => {
        const {client, root} = tree()
        const navigations = []
        window.location.assign = url => navigations.push(url)
        client.http.sendAttributeRequest = async () => ({data: {objects: [
            {
                address: 'root#test',
                result: {},
                effects: {messages: [], redirect: {url: '/next'}},
            },
        ]}})

        await root.save()

        expect(navigations).toEqual(['/next'])
    })
})
