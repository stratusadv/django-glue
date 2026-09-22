import {describe, expect, test} from "bun:test"
import GlueClient from "../src/client"
import {createEntry, createPolicyToken, createStaticData} from "./testUtils"

const formPolicy = {
    name: 'entry_form', namespace: 'form', address: 'form#test',
    attributes: ['validate'], state_snapshot: {name: 'Ada'},
    identity: {target_pk: null},
}
const ownerPolicy = {
    name: 'dashboard', namespace: 'template', address: 'dashboard#test',
    attributes: ['save'], children: {entry_form: 'form#test'}, state_snapshot: {},
}
const formStaticData = createStaticData({callables: {validate: {allowed_arguments: []}}})

function formEntry(overrides = {}) {
    return createEntry({
        policy: {...formPolicy, ...overrides.policy},
        staticData: {callables: {validate: {allowed_arguments: []}}},
        ...overrides,
    })
}

function reintroducedFormEntry(policyToken) {
    return {
        address: 'form#test',
        policy_token: policyToken,
        static_data: formStaticData,
        computed_data: {},
        loading_strategy: 'eager',
    }
}

function dashboardAndForm() {
    const client = new GlueClient({objects: [
        createEntry({
            policy: ownerPolicy,
            staticData: {
                children: {entry_form: {kind: 'form', nullable: false}},
                callables: {save: {allowed_arguments: []}},
            },
        }),
        formEntry(),
    ]})
    globalThis.Glue = client
    const dashboard = client.template.dashboard
    return {client, dashboard, form: dashboard.entry_form}
}

describe('child reintroduction after policy expiry', () => {
    test('the child record knows its owner and canonical path', () => {
        const {form} = dashboardAndForm()

        expect(form._record.owner)
            .toEqual({address: 'dashboard#test', path: 'entry_form'})
    })

    test('a policy_expired child is repaired through its owner and retried once', async () => {
        const {client, form} = dashboardAndForm()
        const originalToken = form._record.policyToken
        const freshToken = createPolicyToken({...formPolicy, created_at: 2})
        const requests = []
        client.http.sendAttributeRequest = async (params) => {
            requests.push(params)
            if (params.attribute === 'validate') {
                if (params.policyToken === originalToken) {
                    return {data: {objects: [{
                        address: 'form#test',
                        error: {code: 'policy_expired', message: 'policy expired'},
                    }]}}
                }
                return {data: {objects: [{address: 'form#test', result: {valid: true}}]}}
            }
            return {data: {objects: [
                {address: 'dashboard#test'},
                reintroducedFormEntry(freshToken),
            ]}}
        }

        const result = await form.validate()

        expect(result).toEqual({valid: true})
        expect(requests).toHaveLength(3)
        expect(requests[0].address).toBe('form#test')
        expect(requests[0].attribute).toBe('validate')
        expect(requests[1].address).toBe('dashboard#test')
        expect(requests[1].attribute).toBeUndefined()
        expect(requests[1].reintroduce).toEqual(['entry_form'])
        expect(requests[2].address).toBe('form#test')
        expect(requests[2].attribute).toBe('validate')
        expect(requests[2].policyToken).toBe(freshToken)
        expect(form._record.stale).toBe(false)
    })

    test('a failed repair rejects with a recoverable error that names the owner', async () => {
        const {client, form} = dashboardAndForm()
        client.http.sendAttributeRequest = async (params) => {
            if (params.attribute === 'validate') {
                return {data: {objects: [{
                    address: 'form#test',
                    error: {code: 'policy_expired', message: 'policy expired'},
                }]}}
            }
            return {data: {objects: [{
                address: 'dashboard#test',
                error: {code: 'not_authorized', message: 'denied'},
            }]}}
        }

        let error
        try {
            await form.validate()
        } catch (caught) {
            error = caught
        }

        expect(error?.name).toBe('GlueAddressError')
        expect(error.code).toBe('policy_expired')
        expect(error.owner).toEqual({name: 'dashboard', address: 'dashboard#test'})
        expect(form._record.stale).toBe(true)
    })

    test('a stale proxy rejects further calls without a round trip', async () => {
        const {client, form} = dashboardAndForm()
        form._record.stale = true
        let calls = 0
        client.http.sendAttributeRequest = async () => {
            calls++
            return {data: {objects: [{address: 'form#test', result: {valid: true}}]}}
        }

        let error
        try {
            await form.validate()
        } catch (caught) {
            error = caught
        }

        expect(calls).toBe(0)
        expect(error?.code).toBe('policy_expired')
        expect(error.owner).toEqual({name: 'dashboard', address: 'dashboard#test'})
    })

    test('in-progress work survives the reintroduction and is resent on the retry', async () => {
        const {client, form} = dashboardAndForm()
        form.name = 'In progress'
        const originalToken = form._record.policyToken
        const repairToken = createPolicyToken({...formPolicy, created_at: 2})
        const acknowledgedToken = createPolicyToken({
            ...formPolicy,
            state_snapshot: {name: 'In progress'},
        })
        const validateRequests = []
        client.http.sendAttributeRequest = async (params) => {
            if (params.attribute === 'validate') {
                validateRequests.push(params)
                if (params.policyToken === originalToken) {
                    return {data: {objects: [{
                        address: 'form#test',
                        error: {code: 'policy_expired', message: 'policy expired'},
                    }]}}
                }
                return {data: {objects: [{
                    address: 'form#test',
                    policy_token: acknowledgedToken,
                    result: {valid: true},
                }]}}
            }
            return {data: {objects: [
                {address: 'dashboard#test'},
                reintroducedFormEntry(repairToken),
            ]}}
        }

        await form.validate()

        expect(form.name).toBe('In progress')
        expect(validateRequests).toHaveLength(2)
        expect(validateRequests[0].updates.name).toBe('In progress')
        expect(validateRequests[1].policyToken).toBe(repairToken)
        expect(validateRequests[1].updates.name).toBe('In progress')
    })

    test('an expired root is not repaired and reports no owner', async () => {
        const client = new GlueClient({objects: [createEntry()]})
        globalThis.Glue = client
        const gorilla = client.model.gorilla
        let calls = 0
        client.http.sendAttributeRequest = async () => {
            calls++
            return {data: {objects: [{
                address: 'gorilla#test',
                error: {code: 'policy_expired', message: 'policy expired'},
            }]}}
        }

        let error
        try {
            await gorilla.save()
        } catch (caught) {
            error = caught
        }

        expect(calls).toBe(1)
        expect(error?.code).toBe('policy_expired')
        expect(error.owner).toBeNull()
    })
})
