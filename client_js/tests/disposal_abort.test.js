import {describe, expect, test} from "bun:test"
import GlueClient from "../src/client"
import {createEntry} from "./testUtils"

function pendingUntilAborted(requests) {
    return request => new Promise((_resolve, reject) => {
        requests.push(request)
        request.signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')))
    })
}

describe('disposal aborts in-flight requests', () => {
    test('a single-address call is aborted and resolves as discarded', async () => {
        const client = new GlueClient({objects: [createEntry()]})
        const gorilla = client.model.gorilla
        const requests = []
        client.http.sendAttributeRequest = pendingUntilAborted(requests)

        const pending = gorilla.save()
        await Promise.resolve()
        await Promise.resolve()
        gorilla.$dispose()

        expect(await pending).toBeUndefined()
        expect(requests[0].signal.aborted).toBeTrue()
        expect(gorilla._record.inFlightController).toBeNull()
    })

    test('a call carrying companions is shared and not abortable', async () => {
        const client = new GlueClient({objects: [
            createEntry(),
            createEntry({policy: {name: 'other', address: 'other#test'}}),
        ]})
        const gorilla = client.model.gorilla
        const other = client._registry.getRecord('other#test')
        const requests = []
        client.http.sendAttributeRequest = pendingUntilAborted(requests)

        gorilla._callAttribute('save', {}, {companions: [other]})
        await Promise.resolve()
        await Promise.resolve()

        expect(requests[0].signal).toBeNull()
        expect(gorilla._record.inFlightController).toBeNull()
    })

    test('the transport chains a caller signal into its own controller', async () => {
        const client = new GlueClient({objects: [createEntry()]})
        const caller = new AbortController()
        let transportSignal = null
        const originalFetch = globalThis.fetch
        globalThis.fetch = (_url, options) => new Promise((_resolve, reject) => {
            transportSignal = options.signal
            options.signal.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')))
        })
        try {
            const pending = client.http.sendRequest('/x/', {method: 'POST', signal: caller.signal})
            caller.abort()
            await expect(pending).rejects.toThrow()
            expect(transportSignal.aborted).toBeTrue()
        } finally {
            globalThis.fetch = originalFetch
        }
    })
})
