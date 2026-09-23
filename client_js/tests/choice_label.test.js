import {describe, expect, test} from "bun:test"
import GlueClient from "../src/client"
import {createEntry} from "./testUtils"

function statusField() {
    const entry = createEntry({
        policy: {state_snapshot: {status: 'open'}},
        staticData: {fields: {
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

    test('strips markup from the text label', () => {
        const field = statusField()

        expect(field.choiceLabelText({value: 2, label: '<b>Grappling</b>', has_html_label: true}))
            .toBe('Grappling')
        expect(field.choiceLabelText({value: 1, label: 'Fish & Chips'})).toBe('Fish & Chips')
    })

    test('treats missing labels as empty strings', () => {
        const field = statusField()

        expect(field.choiceLabelHtml({value: 3})).toBe('')
        expect(field.choiceLabelHtml(null)).toBe('')
    })
})
