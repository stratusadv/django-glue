import {describe, expect, test} from "bun:test"
import GlueClient from "../src/client"
import {attributeResponse, createEntry, createPolicyToken} from "./testUtils"

function deferred() {
    let resolve
    let reject
    const promise = new Promise((onResolve, onReject) => {
        resolve = onResolve
        reject = onReject
    })
    return {promise, resolve, reject}
}

function model() {
    const client = new GlueClient({objects: [createEntry({
        computedData: {fields: {name: {errors: []}}},
    })]})
    return {client, proxy: client.model.gorilla}
}

describe('address record state model', () => {
    test('derives outgoing updates from editable leaves only', () => {
        const {proxy} = model()
        proxy.name = 'Michael'
        proxy._record.reactiveValues.id = 9

        expect(proxy._record.captureRequest().updates).toEqual({name: 'Michael'})
    })

    test('keeps raw JSON wire values without field-type parsing', () => {
        const {proxy} = model()
        expect(proxy.birthday).toBe('1971-07-04')
        proxy.birthday = '2001-02-03'
        expect(proxy.$fields.birthday.value).toBe('2001-02-03')
    })

    test('preserves newer typing when an acknowledgement returns', async () => {
        const {client, proxy} = model()
        const pending = deferred()
        client.http.sendAttributeRequest = async () => pending.promise
        proxy.name = 'AB'
        const request = proxy.save()
        await Promise.resolve()
        proxy.name = 'ABC'
        pending.resolve(attributeResponse('gorilla#test', {
            policy_token: createPolicyToken({
                state_snapshot: {id: 1, name: 'AB', birthday: '1971-07-04'},
            }),
            result: {},
        }))
        await request

        expect(proxy.name).toBe('ABC')
        expect(proxy._record.canonical.name).toBe('AB')
        expect(proxy._record.captureRequest().updates).toEqual({name: 'ABC'})
    })

    test('accepts a same-path server change without a newer mutation', async () => {
        const {client, proxy} = model()
        client.http.sendAttributeRequest = async () => attributeResponse('gorilla#test', {
            policy_token: createPolicyToken({
                state_snapshot: {id: 1, name: 'Normalized', birthday: '1971-07-04'},
            }),
            result: {},
        })
        proxy.name = ' submitted '
        await proxy.save()
        expect(proxy.name).toBe('Normalized')
    })

    test('retains omitted token and computed halves', async () => {
        const {client, proxy} = model()
        const token = proxy._record.policyToken
        client.http.sendAttributeRequest = async () => attributeResponse('gorilla#test', {result: {ok: true}})
        await proxy.save()

        expect(proxy._record.policyToken).toBe(token)
        expect(proxy.$fields.name.errors).toEqual([])
    })

    test('patches stable field proxies with fresh computed output', async () => {
        const {client, proxy} = model()
        const field = proxy.$fields.name
        client.http.sendAttributeRequest = async () => attributeResponse('gorilla#test', {
            computed_data: {fields: {name: {errors: ['Required']}}},
            result: {},
        })
        await proxy.save()

        expect(proxy.$fields.name).toBe(field)
        expect(field.errors).toEqual(['Required'])
        expect(proxy.hasErrors('name')).toBeTrue()
    })

    test('serializes requests per address and captures queued updates at send time', async () => {
        const {client, proxy} = model()
        const first = deferred()
        const sent = []
        client.http.sendAttributeRequest = request => {
            sent.push(request.updates)
            return sent.length === 1 ? first.promise : Promise.resolve(attributeResponse('gorilla#test', {result: {}}))
        }
        proxy.name = 'AB'
        const firstCall = proxy.save()
        await Promise.resolve()
        const secondCall = proxy.save()
        proxy.name = 'ABC'
        expect(sent).toEqual([{name: 'AB'}])
        first.resolve(attributeResponse('gorilla#test', {
            policy_token: createPolicyToken({
                state_snapshot: {id: 1, name: 'AB', birthday: '1971-07-04'},
            }),
            result: {},
        }))
        await firstCall
        await secondCall

        expect(sent).toEqual([{name: 'AB'}, {name: 'ABC'}])
    })

    test('releases the address queue after a failed operation', async () => {
        const {client, proxy} = model()
        let calls = 0
        client.http.sendAttributeRequest = async () => {
            calls += 1
            if (calls === 1) throw new Error('offline')
            return attributeResponse('gorilla#test', {result: 'ok'})
        }

        await expect(proxy.save()).rejects.toThrow('offline')
        expect(await proxy.save()).toBe('ok')
    })
})
