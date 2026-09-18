import {describe, expect, test} from "bun:test"
import GlueConfig from "../src/config"
import GlueHttp from "../src/http"
import GlueModelProxy from "../src/proxies/model"
import {createMetadata, createPolicy} from "./testUtils"

function makeSkillField(labelIsHtml) {
    const object = new GlueModelProxy({
        http: new GlueHttp(new GlueConfig()),
        policy: createPolicy({attributes: ['skill']}),
        state: {skill: {value: null}},
        metadata: createMetadata({fields: {
            skill: {
                type: 'ForeignKey',
                choice_model_path: 'test_project.gorilla.models.Skill',
                choices: [],
                choices_label_is_html: labelIsHtml,
            },
        }}),
    })
    object._loaded = true
    return object.$fields.skill
}

describe('relation field choiceLabelHtml', () => {
    test('escapes plain labels for safe html rendering', () => {
        const field = makeSkillField(false)
        const choice = {value: 1, label: 'Fish & Chips <b>bold</b>'}

        expect(field.choiceLabelHtml(choice)).toBe('Fish &amp; Chips &lt;b&gt;bold&lt;/b&gt;')
    })

    test('returns html labels verbatim', () => {
        const field = makeSkillField(true)
        const choice = {value: 2, label: '<b>Grappling</b>'}

        expect(field.choiceLabelHtml(choice)).toBe('<b>Grappling</b>')
    })

    test('treats missing labels as empty strings', () => {
        const field = makeSkillField(false)

        expect(field.choiceLabelHtml({value: 3})).toBe('')
        expect(field.choiceLabelHtml(null)).toBe('')
    })
})

describe('static choice field choiceLabelHtml', () => {
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
