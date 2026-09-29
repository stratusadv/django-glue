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

    test('sends the mounted children a component reports', async () => {
        const calls = mockOperationFetch()
        const http = new GlueHttp(new GlueConfig())

        await http.sendAttributeRequest({address: 'a#1', policyToken: 't', mounted: ['a#1[x]']})

        expect(JSON.parse(calls[0].options.body.get('objects'))[0].mounted).toEqual(['a#1[x]'])
    })

    test('a batch sends its requests as one post and hands each caller its own entries', async () => {
        const calls = mockOperationFetch({objects: [
            {address: 'a#1', result: 1},
            {address: 'a#1[child]', result: null},
            {address: 'b#2', result: 2},
        ]})
        const http = new GlueHttp(new GlueConfig())
        const batch = http.batch(2)

        const [first, second] = await Promise.all([
            http.sendAttributeRequest({address: 'a#1', policyToken: 't1', attribute: '$receive', batch}),
            http.sendAttributeRequest({address: 'b#2', policyToken: 't2', attribute: '$receive', batch}),
        ])

        expect(calls).toHaveLength(1)
        expect(JSON.parse(calls[0].options.body.get('objects')).map(entry => entry.address)).toEqual(['a#1', 'b#2'])
        expect(first.data.objects.map(entry => entry.address)).toEqual(['a#1', 'a#1[child]'])
        expect(second.data.objects.map(entry => entry.address)).toEqual(['b#2'])
    })

    test('a batch that never fills sends what it has on the next task', async () => {
        const calls = mockOperationFetch({objects: [{address: 'a#1', result: 1}]})
        const http = new GlueHttp(new GlueConfig())

        const response = await http.sendAttributeRequest({
            address: 'a#1', policyToken: 't1', attribute: '$receive', batch: http.batch(3),
        })

        expect(calls).toHaveLength(1)
        expect(response.data.objects).toEqual([{address: 'a#1', result: 1}])
    })
})
