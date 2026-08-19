import {describe, expect, test} from "bun:test"
import GlueConfig from "../src/config"
import GlueHttp from "../src/http"
import GlueFormProxy from "../src/proxies/form"
import GlueFunctionProxy from "../src/proxies/function"
import GlueModelProxy from "../src/proxies/model"
import {createMetadata, createPolicy, createPolicyToken, createState} from "./testUtils"

describe('fields, forms, and functions', () => {
    test('field proxies expose errors, primitive conversion, and object members', () => {
        const object = new GlueModelProxy({
            http: new GlueHttp(new GlueConfig()),
            policy: createPolicy({attributes: ['id', 'name']}),
            state: {
                id: {value: 1},
                name: {value: {label: 'Koko'}, errors: ['Required', 'Invalid']},
            },
            metadata: createMetadata(),
        })
        object._loaded = true

        expect(object.$fields.name.errorText).toBe('Required, Invalid')
        expect(object.$fields.name.hasErrors).toBe(true)
        expect(object.$fields.name.label).toBe('Name')
    })

    test('form proxies use the same field-backed state contract', () => {
        const form = new GlueFormProxy({
            http: new GlueHttp(new GlueConfig()),
            policy: createPolicy({name: 'gorilla_form', namespace: 'form', attributes: ['name']}),
            state: createState({instance_data: {name: ''}}),
            metadata: createMetadata({namespace: 'form'}),
        })
        form._loaded = true

        expect(form.name).toBe('')
        form.name = 'Koko'
        expect(form.$fields.name.value).toBe('Koko')
        expect(form.hasErrors()).toBe(false)
    })

    test('function proxies filter kwargs to declared parameters and unwrap result', async () => {
        let kwargs
        global.fetch = async (_url, options) => {
            kwargs = JSON.parse(options.body.get('kwargs'))
            return new Response(JSON.stringify({result: {result: 12}, state: {}, policy_token: createPolicyToken(), metadata: {}}), {
                status: 200,
                headers: {'Content-Type': 'application/json'},
            })
        }
        const functionProxy = GlueFunctionProxy.create({
            http: new GlueHttp(new GlueConfig()),
            policy: createPolicy({
                name: 'add',
                namespace: 'function',
                identity: {params: ['left', 'right']},
                attributes: ['execute'],
            }),
            metadata: {namespace: 'function', params: ['left', 'right'], attributes: {execute: {namespace: 'callable'}}},
        })

        expect(await functionProxy({left: 5, right: 7, ignored: true})).toBe(12)
        expect(kwargs).toEqual({left: 5, right: 7})
    })
})
