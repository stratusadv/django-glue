import {describe, expect, test} from "bun:test"
import GlueConfig from "../src/config"
import GlueHttp from "../src/http"
import GlueModelProxy from "../src/proxies/model"
import GlueQuerySetProxy from "../src/proxies/queryset"
import {RelationFieldGlue} from "../src/proxies/fields"
import {createMetadata, createPolicy, createState} from "./testUtils"

function http() {
    return new GlueHttp(new GlueConfig())
}

describe('frontend coverage edges', () => {
    test('model readonly attributes and named error checks are available', () => {
        const object = new GlueModelProxy({
            http: http(),
            policy: createPolicy({attributes: ['id', 'display_name', 'name']}),
            state: {id: {value: 1}, display_name: {value: 'Koko'}, name: {value: 'Koko', errors: ['Required']}},
            metadata: createMetadata({attributes: {
                display_name: {namespace: 'readonly'},
                name: {namespace: 'field', type: 'CharField', label: 'Name'},
            }}),
        })
        object._loaded = true

        expect(object.display_name).toBe('Koko')
        expect(object.hasErrors('name')).toBe(true)
        expect(object.hasErrors('display_name')).toBe(false)
        expect(object.$key).toBe(1)
    })

    test('field setters initialize missing field state and proxy object members', () => {
        const object = new GlueModelProxy({
            http: http(),
            policy: createPolicy({attributes: ['name', 'items']}),
            state: {},
            metadata: createMetadata({fields: {
                name: {type: 'CharField'},
                items: {type: 'JSONField'},
            }}),
        })
        object._loaded = true

        object.name = 'Koko'
        object.$fields.items.value = {enabled: false}
        object.$fields.items.enabled = true

        expect(object._state.name.value).toBe('Koko')
        expect(object.$fields.items.enabled).toBe(true)
        expect('enabled' in object.$fields.items).toBe(true)
    })

    test('relation fields without a callable return current choices without requesting', async () => {
        RelationFieldGlue.loadingCache.clear()
        const object = new GlueModelProxy({
            http: http(),
            policy: createPolicy({attributes: ['owner']}),
            state: {owner: {value: 1}},
            metadata: createMetadata({fields: {
                owner: {type: 'ForeignKey', choice_model_path: 'Owner', choices: []},
            }}),
        })
        object._loaded = true

        expect(await object.$fields.owner.ensureChoices()).toEqual([])
        object.$fields.owner.pk = 2
        expect(object.$fields.owner.pk).toBe(2)
    })

    test('queryset new returns a model proxy', async () => {
        // The `new` attribute returns a result containing policy/state/metadata for the new model
        global.fetch = async () => new Response(JSON.stringify({
            result: {
                policy: {name: 'gorillas.3', namespace: 'model'},
                state: {id: {value: 3}},
                metadata: {},
            },
        }), {status: 200, headers: {'Content-Type': 'application/json'}})
        const object = new GlueQuerySetProxy({
            http: http(),
            policy: createPolicy({name: 'gorillas', namespace: 'querySet', attributes: ['new']}),
            state: {},
            metadata: createMetadata({namespace: 'querySet', attributes: {new: {namespace: 'callable'}}}),
        })

        const newModel = await object.new()
        expect(newModel).toBeInstanceOf(GlueModelProxy)
        expect(newModel._loaded).toBe(true)
    })

    test('multipart requests append FileList and file arrays', async () => {
        class TestFileList extends Array {}
        const previousFileList = global.FileList
        global.FileList = TestFileList
        const list = new TestFileList(new File(['a'], 'a.txt'), new File(['b'], 'b.txt'))
        const file = new File(['c'], 'c.txt')
        let body
        global.fetch = async (_url, options) => {
            body = options.body
            return new Response('{}', {status: 200})
        }
        const glueHttp = http()
        glueHttp._extractFiles = () => ({files: {uploads: list, attachments: [file]}, data: {}})

        await glueHttp.sendAttributeRequest({name: 'gorilla', policy: {}, state: {}, attribute: 'save'})

        expect(body.getAll('uploads')).toHaveLength(2)
        expect(body.getAll('attachments')).toHaveLength(1)
        global.FileList = previousFileList
    })
})
