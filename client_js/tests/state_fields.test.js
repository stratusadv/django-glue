import {describe, expect, test} from "bun:test"
import GlueConfig from "../src/config"
import GlueHttp from "../src/http"
import GlueModelProxy from "../src/proxies/model"
import {createMetadata, createPolicy} from "./testUtils"

describe('state and field edge behavior', () => {
    test('state attributes and recursive state merges preserve the state object', () => {
        const object = new GlueModelProxy({
            http: new GlueHttp(new GlueConfig()),
            policy: createPolicy({attributes: ['settings', 'settings.mode']}),
            state: {'settings.mode': 'compact', settings: {nested: {enabled: true}}},
            metadata: {
                namespace: 'model',
                attributes: {
                    settings: {namespace: 'container'},
                    'settings.mode': {namespace: 'state'},
                },
            },
        })
        const state = object._state

        expect(object.settings.mode).toBe('compact')
        object.settings.mode = 'expanded'
        object._applyState({'settings.mode': 'expanded', settings: {}})

        expect(object._state).toBe(state)
        expect(object.settings.mode).toBe('expanded')
        expect(object._state.settings.nested).toBeUndefined()
    })

    test('field proxies convert dates, arrays, nulls, and JSON values', () => {
        const object = new GlueModelProxy({
            http: new GlueHttp(new GlueConfig()),
            policy: createPolicy({attributes: ['date', 'items', 'empty']}),
            state: {
                date: {value: new Date('2026-01-01T00:00:00Z')},
                items: {value: ['one', 'two']},
                empty: {value: null},
            },
            metadata: createMetadata({fields: {
                date: {type: 'DateField'},
                items: {type: 'JSONField'},
                empty: {type: 'CharField'},
            }}),
        })
        object._loaded = true

        expect(Number(object.$fields.date)).toBe(new Date('2026-01-01T00:00:00Z').valueOf())
        expect(String(object.$fields.items)).toBe('one,two')
        expect(String(object.$fields.empty)).toBe('')
        expect(JSON.stringify(object.$fields.items)).toBe('["one","two"]')
    })
})
