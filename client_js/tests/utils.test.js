import {describe, expect, test} from "bun:test"
import {cloneValue, isPlainObject, parseJsonScriptById, serializeValue} from "../src/utils"

describe('frontend value utilities', () => {
    test('clones nested values without sharing mutable objects', () => {
        const source = {nested: {items: [1, 2]}, date: new Date('2026-01-01T00:00:00Z')}
        const clone = cloneValue(source)

        expect(clone).toEqual(source)
        expect(clone).not.toBe(source)
        expect(clone.nested).not.toBe(source.nested)
        expect(clone.date).not.toBe(source.date)
        expect(isPlainObject(clone.nested)).toBe(true)
        expect(isPlainObject(clone.date)).toBe(false)
    })

    test('serializes dates without coercing wire values on read', () => {
        const date = new Date('2026-01-01T00:00:00Z')
        expect(serializeValue({date, ignored: () => {}, _private: true})).toEqual({date: date.toISOString()})
    })

    test('reads JSON embedded in a script element', () => {
        document.body.innerHTML = '<script id="manifest" type="application/json">{"name":"gorilla"}</script>'

        expect(parseJsonScriptById('manifest')).toEqual({name: 'gorilla'})
    })
})
