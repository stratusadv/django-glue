import {describe, expect, test} from "bun:test"
import GlueConfig from "../src/config"
import GlueHttp from "../src/http"
import {GlueHttpError} from "../src/errors"

function http() {
    return new GlueHttp(new GlueConfig())
}

describe('GlueHttp edge cases', () => {
    test('sends method, JSON content type, CSRF token, and returns response data', async () => {
        document.cookie = 'csrftoken=token%201'
        let request
        global.fetch = async (_url, options) => {
            request = options
            return new Response(JSON.stringify({ok: true}), {status: 200})
        }

        const result = await http().sendRequest('/endpoint', {
            method: 'PUT',
            contentType: 'application/json',
            body: '{}',
        })

        expect(request.method).toBe('PUT')
        expect(request.headers).toEqual({
            'Content-Type': 'application/json',
            'X-CSRFToken': 'token 1',
        })
        expect(result.data).toEqual({ok: true})
        expect(result.body).toBe('{"ok":true}')
    })

    test('omits CSRF when explicitly disabled', async () => {
        let request
        global.fetch = async (_url, options) => {
            request = options
            return new Response('{}', {status: 200})
        }

        await http().sendRequest('/endpoint', {csrfProtected: false})

        expect(request.headers).toEqual({})
    })

    test('builds structured GlueHttpErrors from JSON and text responses', async () => {
        global.fetch = async () => new Response(JSON.stringify({
            error: {message: 'Denied', code: 'forbidden', detail: 'no access'},
        }), {status: 403})

        await expect(http().sendRequest('/denied')).rejects.toMatchObject({
            name: 'GlueHttpError',
            status: 403,
            message: 'Denied',
            code: 'forbidden',
            payload: {message: 'Denied', code: 'forbidden', detail: 'no access'},
        })

        global.fetch = async () => new Response('upstream failed', {status: 502})
        const error = await http()._buildRequestError(new Response('upstream failed', {status: 502}))
        expect(error).toBeInstanceOf(GlueHttpError)
        expect(error.message).toBe('upstream failed')
    })

    test('builds structured GlueHttpErrors from Glue response error envelopes', async () => {
        global.fetch = async () => new Response(JSON.stringify({
            result: {
                error: {
                    message: 'Policy denied',
                    code: 'proxy_access_denied',
                    status: 403,
                    details: {attribute: 'save'},
                },
            },
            messages: [],
        }), {status: 403})

        await expect(http().sendRequest('/denied')).rejects.toMatchObject({
            name: 'GlueHttpError',
            status: 403,
            message: 'Policy denied',
            code: 'proxy_access_denied',
            payload: {
                message: 'Policy denied',
                code: 'proxy_access_denied',
                status: 403,
                details: {attribute: 'save'},
            },
        })
    })

    test('extracts top-level, nested, and array files from serialized state', () => {
        const file = new File(['contents'], 'photo.txt', {type: 'text/plain'})
        const result = http()._extractFiles({
            profile_photo: {value: file},
            nested: {upload: file, name: 'nested'},
            attachments: [file, 'existing'],
            name: 'Koko',
        })

        expect(result.files.profile_photo).toBe(file)
        expect(result.files['nested.upload']).toBe(file)
        expect(result.files.attachments).toEqual([file])
        expect(result.data).toEqual({nested: {name: 'nested'}, attachments: ['existing'], name: 'Koko'})
    })

})
