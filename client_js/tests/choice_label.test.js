import {describe, expect, test} from "bun:test"
import GlueConfig from "../src/config"
import GlueHttp from "../src/http"
import GlueModelProxy from "../src/proxies/model"
import {createMetadata, createPolicy} from "./testUtils"

function makeSkillField() {
    const object = new GlueModelProxy({
        http: new GlueHttp(new GlueConfig()),
        policy: createPolicy({attributes: ['skill']}),
        state: {skill: {value: null}},
        metadata: createMetadata({fields: {
            skill: {
                type: 'ForeignKey',
                choice_model_path: 'test_project.gorilla.models.Skill',
                choices: [],
            },
        }}),
    })
    object._loaded = true
    return object.$fields.skill
}

describe('relation field choice labels', () => {
    test('escapes plain labels for safe html rendering', () => {
        const field = makeSkillField()
        const choice = {value: 1, label: 'Fish & Chips <b>bold</b>'}

        expect(field.choiceLabelHtml(choice)).toBe('Fish &amp; Chips &lt;b&gt;bold&lt;/b&gt;')
    })

    test('returns html labels verbatim', () => {
        const field = makeSkillField()
        const choice = {value: 2, label: '<b>Grappling</b>', has_html_label: true}

        expect(field.choiceLabelHtml(choice)).toBe('<b>Grappling</b>')
    })

    test('strips markup from the text label', () => {
        const field = makeSkillField()

        expect(field.choiceLabelText({value: 2, label: '<b>Grappling</b>', has_html_label: true}))
            .toBe('Grappling')
        expect(field.choiceLabelText({value: 1, label: 'Fish & Chips'}))
            .toBe('Fish & Chips')
    })

    test('treats missing labels as empty strings', () => {
        const field = makeSkillField()

        expect(field.choiceLabelHtml({value: 3})).toBe('')
        expect(field.choiceLabelHtml(null)).toBe('')
    })
})

describe('static choice field choice labels', () => {
    test('escapes labels', () => {
        const object = new GlueModelProxy({
            http: new GlueHttp(new GlueConfig()),
            policy: createPolicy({attributes: ['status']}),
            state: {status: {value: null}},
            metadata: createMetadata({fields: {
                status: {
                    type: 'ChoiceField',
                    choices: [{value: 'calm', label: 'Calm & Steady'}],
                },
            }}),
        })
        object._loaded = true

        expect(object.$fields.status.choiceLabelHtml({value: 'calm', label: 'Calm & Steady'}))
            .toBe('Calm &amp; Steady')
    })
})
