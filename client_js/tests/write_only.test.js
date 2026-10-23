import {describe, expect, test} from "bun:test"
import GlueClient from "../src/client"
import {attributeResponse, createEntry, createPolicyToken} from "./testUtils"

const SNAPSHOT = {id: 1, name: 'Koko', birthday: '1971-07-04'}

function form() {
    const client = new GlueClient({objects: [createEntry({
        staticData: {fields: {
            password: {value_path: 'password', type: 'CharField', label: 'Password', editable: true, write_only: true},
        }},
    })]})
    const sent = []
    client.http.sendAttributeRequest = async (request) => {
        sent.push(request)
        return attributeResponse('gorilla#test', {
            policy_token: createPolicyToken({state_snapshot: {...SNAPSHOT, name: 'Acknowledged'}}),
            computed_data: {fields: {password: {errors: ['Too short.']}}},
            result: {},
        })
    }
    return {proxy: client.model.gorilla, sent}
}

describe('write-only fields (ADR 036)', () => {
    test('send nothing until the user types', () => {
        const {proxy} = form()

        expect(proxy.password).toBeUndefined()
        expect(proxy._record.captureRequest().updates).toEqual({})
    })

    test('keep what the user typed when a response leaves them out', async () => {
        const {proxy} = form()
        proxy.password = 'mulch-season-2026'

        await proxy.save()

        expect(proxy.password).toBe('mulch-season-2026')
        expect(proxy.$fields.password.errors).toEqual(['Too short.'])
        expect(proxy.name).toBe('Acknowledged')
        expect('password' in proxy._record.canonical).toBe(false)
    })

    test('resend the typed value on every call', async () => {
        const {proxy, sent} = form()
        proxy.password = 'mulch-season-2026'

        await proxy.save()
        await proxy.save()

        expect(sent.map(request => request.updates.password)).toEqual(['mulch-season-2026', 'mulch-season-2026'])
    })
})
