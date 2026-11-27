import {describe, expect, test} from "bun:test"
import GlueClient from "../src/client"
import {createEntry} from "./testUtils"

function statusField() {
    const entry = createEntry({
        policy: {state_snapshot: {status: 'open'}},
        staticData: {value_attributes: {
            status: {
                value_path: 'status', type: 'ChoiceField', editable: true,
                choices: [{value: 'open', label: 'Open'}],
            },
        }},
    })
    return new GlueClient({objects: [entry]}).model.gorilla.$fields.status
}

describe('choice field labels', () => {
    test('escapes plain labels for safe html rendering', () => {
        expect(statusField().choiceLabelHtml({value: 1, label: 'Fish & Chips <b>bold</b>'}))
            .toBe('Fish &amp; Chips &lt;b&gt;bold&lt;/b&gt;')
    })

    test('returns formatter html labels verbatim', () => {
        expect(statusField().choiceLabelHtml({value: 2, label: '<b>Grappling</b>', has_html_label: true}))
            .toBe('<b>Grappling</b>')
    })

    test('strips markup and decodes entities from html labels without running markup', () => {
        const field = statusField()

        expect(field.choiceLabelText({value: 2, label: '<b>Grappling</b>', has_html_label: true}))
            .toBe('Grappling')
        expect(field.choiceLabelText({
            value: 3,
            label: 'Acme &amp; Co &gt; Portal &#x27;26',
            has_html_label: true,
        })).toBe("Acme & Co > Portal '26")
        expect(field.choiceLabelText({
            value: 4,
            label: '<img src="x" onerror="globalThis.__choiceXss = true">Safe',
            has_html_label: true,
        })).toBe('Safe')
        expect(globalThis.__choiceXss).toBeUndefined()
        expect(field.choiceLabelText({value: 1, label: 'Fish & Chips <raw>'})).toBe('Fish & Chips <raw>')
    })

    test('treats missing labels as empty strings', () => {
        const field = statusField()

        expect(field.choiceLabelHtml({value: 3})).toBe('')
        expect(field.choiceLabelHtml(null)).toBe('')
    })
})
