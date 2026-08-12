import {describe, expect, test} from "bun:test"
import GlueConfig from "../src/config"
import GlueHttp from "../src/http"
import GlueClient from "../src/client"
import GlueModelProxy from "../src/proxies/model"
import GlueQuerySetProxy from "../src/proxies/queryset"
import BaseGlueProxy from "../src/proxies/base"
import GlueView from "../src/view"
import {GlueProxyError} from "../src/errors"
import {createMetadata, createPolicy, createState} from "./testUtils"

function http() {
    return new GlueHttp(new GlueConfig())
}

describe('frontend edge cases', () => {
    test('client rejects invalid manifests', () => {
        expect(() => new GlueClient({manifest_list: [{policy: {namespace: 'model'}}]})).toThrow(GlueProxyError)
    })

    test('client registers custom namespaces as base proxies', () => {
        const client = new GlueClient({
            manifest_list: [{
                policy: {name: 'dashboard', namespace: 'timeEntryDashboard', attributes: []},
                metadata: {},
                state: {},
            }],
        })

        expect(client.timeEntryDashboard.dashboard).toBeInstanceOf(BaseGlueProxy)
    })

    test('proxy error listeners receive failed attribute requests', async () => {
        global.fetch = async () => new Response(JSON.stringify({error: {message: 'Failed'}}), {status: 500})
        const proxy = new GlueModelProxy({
            http: http(),
            policy: createPolicy({attributes: ['save']}),
            state: {},
            metadata: createMetadata({attributes: {save: {namespace: 'callable'}}}),
        })
        let received
        proxy.onError(payload => { received = payload })

        expect(await proxy.save()).toBeUndefined()
        expect(received.attribute).toBe('save')
        expect(received.proxy).toBe(proxy)
        expect(received.error.status).toBe(500)
    })

    test('model delete callable exists when exposed by policy', async () => {
        global.fetch = async () => new Response(JSON.stringify({
            result: null, state: {}, policy: {}, metadata: {},
        }), {status: 200, headers: {'Content-Type': 'application/json'}})
        const row = new GlueModelProxy({
            http: http(),
            policy: createPolicy({name: 'gorillas.1', attributes: ['id', 'delete']}),
            state: createState({instance_data: {id: 1}}),
            metadata: createMetadata({attributes: {delete: {namespace: 'callable'}}}),
        })

        // delete is exposed as a callable attribute, not as a special wrapper
        expect(typeof row.delete).toBe('function')
        await row.delete()
        // model proxies do not implicitly mutate parent collections on delete
    })

    test('choice fields expose selection helpers', () => {
        const object = new GlueModelProxy({
            http: http(),
            policy: createPolicy({attributes: ['status', 'temperaments', 'skills']}),
            state: {
                status: {value: 'done'},
                temperaments: {value: ['calm']},
                skills: {value: [1]},
            },
            metadata: createMetadata({
                fields: {
                    status: {type: 'CharField', choices: [
                        {value: 'done', label: 'Done'},
                        {value: 'new', label: 'New'},
                    ]},
                    temperaments: {type: 'MultipleChoiceField', choices: [
                        {value: 'calm', label: 'Calm'},
                        {value: 'alert', label: 'Alert'},
                    ]},
                    skills: {
                        type: 'ManyToManyField',
                        choice_model_path: 'Skill',
                        choices: [
                            {value: 1, label: 'Grappling', obj: {pk: 1, __str__: 'Grappling'}},
                            {value: 2, label: 'Climbing', obj: {pk: 2, __str__: 'Climbing'}},
                            {value: 'skill-uuid', label: 'Foraging', obj: {pk: 'skill-uuid', __str__: 'Foraging'}},
                        ],
                    },
                },
            }),
        })
        object._loaded = true
        object.$fields.skills._mergeChoices([
            {value: 1, label: 'Grappling', obj: {pk: 1, __str__: 'Grappling'}},
            {value: 2, label: 'Climbing', obj: {pk: 2, __str__: 'Climbing'}},
            {value: 'skill-uuid', label: 'Foraging', obj: {pk: 'skill-uuid', __str__: 'Foraging'}},
        ])

        expect(object.$fields.status.selectedChoice).toEqual({value: 'done', label: 'Done'})
        expect(object.$fields.status.selectedChoice.label).toBe('Done')
        expect(object.$fields.temperaments.selectedChoices).toEqual([{value: 'calm', label: 'Calm'}])
        expect(object.$fields.temperaments.addChoice('alert').hasChoiceSelected('alert')).toBe(true)
        expect(object.$fields.temperaments.removeChoice('calm').hasChoiceSelected('calm')).toBe(false)
        expect(object.$fields.temperaments.toggleChoice('alert').hasChoiceSelected('alert')).toBe(false)
        expect(object.$fields.skills.selectedPks).toEqual([1])
        expect(object.$fields.skills.selectedChoices).toEqual([
            {value: 1, label: 'Grappling', obj: {pk: 1, __str__: 'Grappling'}},
        ])
        expect(object.$fields.skills.addChoice(2).hasChoiceSelected(2)).toBe(true)
        expect(object.$fields.skills.removeChoice(1).hasChoiceSelected(1)).toBe(false)
        expect(object.$fields.skills.toggleChoice(2).hasChoiceSelected(2)).toBe(false)
        expect(object.$fields.skills.addChoice('skill-uuid').hasChoiceSelected('skill-uuid')).toBe(true)
    })

    test('view GET requests preserve the GET method in the view payload', async () => {
        happyDOM.setURL('http://localhost/')
        let body
        globalThis.Glue = {loadManifests: () => {}}
        const view = new GlueView({
            _config: {glueViewUrlPath: '/view/'},
            sendRequest: async (_url, options) => {
                body = JSON.parse(options.body)
                return {data: {html: ''}}
            },
        }, '/partial/')

        await view.get({page: 2})

        expect(body.method).toBe('GET')
        expect(body.view_payload).toEqual({page: 2})
    })
})
