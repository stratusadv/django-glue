import {describe, expect, test} from "bun:test"
import GlueConfig from "../src/config"
import GlueHttp from "../src/http"
import {createPolicy, createState, mockOperationFetch} from "./testUtils"

describe('GlueHttp', () => {
    test('sends attribute requests to the adapter endpoint as multipart form data', async () => {
        const calls = mockOperationFetch()
        const http = new GlueHttp(new GlueConfig())
        const policy = createPolicy()
        const updates = createState()

        await http.sendAttributeRequest({
            address: policy.address,
            policyToken: policy.token,
            updates,
            attribute: 'save',
            kwargs: {},
        })

        expect(calls[0].url).toBe('/__dg__/callable_attribute/')
        expect(calls[0].options.method).toBe('POST')
        expect(calls[0].options.body).toBeInstanceOf(FormData)
        expect(JSON.parse(calls[0].options.body.get('objects'))).toEqual([{
            address: policy.address,
            policy_token: policy.token,
            updates,
            call: {attribute: 'save', kwargs: {}},
        }])
        expect(calls[0].options.body.has('policy')).toBeFalse()
        expect(calls[0].options.body.has('state')).toBeFalse()
    })
})
