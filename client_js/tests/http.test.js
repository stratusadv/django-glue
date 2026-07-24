import {describe, expect, test} from "bun:test"
import GlueConfig from "../src/config"
import GlueHttp from "../src/http"
import {createPolicy, createState, mockOperationFetch} from "./testUtils"

describe('GlueHttp', () => {
    test('sends attribute requests to the adapter endpoint as multipart form data', async () => {
        const calls = mockOperationFetch()
        const http = new GlueHttp(new GlueConfig())
        const policy = createPolicy()
        const state = createState()

        await http.sendAttributeRequest({
            name: 'gorilla',
            policy,
            state,
            attribute: 'save',
            kwargs: {},
        })

        expect(calls[0].url).toBe('/__dg__/callable_attribute/gorilla/save/')
        expect(calls[0].options.method).toBe('POST')
        expect(calls[0].options.body).toBeInstanceOf(FormData)
        expect(JSON.parse(calls[0].options.body.get('policy'))).toEqual(policy)
        expect(JSON.parse(calls[0].options.body.get('state')).name.value).toBe('Koko')
        expect(calls[0].options.body.get('attribute')).toBe('save')
        expect(JSON.parse(calls[0].options.body.get('kwargs'))).toEqual({})
    })
})
