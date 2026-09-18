import {beforeEach, describe, expect, test} from "bun:test"
import GlueClient from "../src/client"
import {createPolicyToken} from "./testUtils"

function clientWith(manifests) {
    return new GlueClient({
        manifest_list: manifests,
        urls: {},
        config: {},
    })
}

function componentManifest(name) {
    return {
        is_glue_manifest: true,
        policy_token: createPolicyToken({name, namespace: 'component'}),
        metadata: {},
        state: {},
    }
}

describe('Sweeping disposed components', () => {
    beforeEach(() => {
        document.body.innerHTML = ''
    })

    test('a component whose root left the document is dropped', () => {
        document.body.innerHTML = '<div data-glue="day_a1"></div>'
        const client = clientWith([componentManifest('day_a1'), componentManifest('day_a2')])

        expect(Object.keys(client.component).sort()).toEqual(['day_a1', 'day_a2'])

        const disposed = client.sweepDisposedComponents()

        expect(disposed).toEqual(['day_a2'])
        expect(Object.keys(client.component)).toEqual(['day_a1'])
    })

    test('a component still in the document is kept', () => {
        document.body.innerHTML = '<div data-glue="day_a1"></div>'
        const client = clientWith([componentManifest('day_a1')])

        expect(client.sweepDisposedComponents()).toEqual([])
        expect(client.component.day_a1).toBeDefined()
    })

    test('a week of cards replaced by another week leaves nothing behind', () => {
        // The motivating case: next_week() re-renders the board with new keys,
        // so every previous card's registration is dead the moment it is
        // morphed out.
        const previous = ['d1', 'd2', 'd3'].map(componentManifest)
        const next = ['d4', 'd5', 'd6'].map(componentManifest)
        document.body.innerHTML = previous
            .map((_, index) => `<div data-glue="d${index + 1}"></div>`)
            .join('')
        const client = clientWith(previous)

        document.body.innerHTML = '<div data-glue="d4"></div>'
            + '<div data-glue="d5"></div><div data-glue="d6"></div>'
        client.loadManifests(next)

        expect(client.sweepDisposedComponents().sort()).toEqual(['d1', 'd2', 'd3'])
        expect(Object.keys(client.component).sort()).toEqual(['d4', 'd5', 'd6'])
    })

    test('other namespaces are untouched, having no DOM root at all', () => {
        document.body.innerHTML = ''
        const client = clientWith([
            componentManifest('day_a1'),
            {
                is_glue_manifest: true,
                policy_token: createPolicyToken({name: 'gorilla', namespace: 'model'}),
                metadata: {},
                state: {},
            },
        ])

        client.sweepDisposedComponents()

        expect(client.component.day_a1).toBeUndefined()
        expect(client.model.gorilla).toBeDefined()
    })

    test('sweeping before any component is registered is a no-op', () => {
        const client = clientWith([])

        expect(client.sweepDisposedComponents()).toEqual([])
    })
})
