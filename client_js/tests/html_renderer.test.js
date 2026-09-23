import {describe, expect, test} from "bun:test"
import {htmlResultFromResponse} from "../src/htmlRenderer"
import GlueView from "../src/view"

const renderers = {
    result: html => htmlResultFromResponse({html}),
    view: html => {
        happyDOM.setURL('http://localhost/')
        return new GlueView({
            _config: {glueViewMediaType: 'application/vnd.django-glue.view+json'},
            sendRequest: async () => ({data: {is_glue_template_response: true, html, objects: []}}),
        }, '/fragment/')
    },
}

for (const [name, createRenderer] of Object.entries(renderers)) {
    describe(`${name} shared HTML renderer`, () => {
        test('morphs text while retaining keyed nodes and ignored widgets', async () => {
            document.body.innerHTML = '<div id="target"><p key="a">Old</p><div data-morph-ignore>Widget</div></div>'
            const target = document.querySelector('#target')
            const paragraph = target.firstElementChild
            const renderer = createRenderer('<p key="a">New</p><div data-morph-ignore></div><b>Added</b>')

            await renderer.renderInnerHtml(target)

            expect(document.querySelector('#target')).toBe(target)
            expect(target.firstElementChild).toBe(paragraph)
            expect(paragraph.textContent).toBe('New')
            expect(target.querySelector('[data-morph-ignore]').textContent).toBe('Widget')
            expect(target.lastElementChild.textContent).toBe('Added')
        })

        test('outer morph preserves local Alpine state and mounted node identity', async () => {
            document.body.innerHTML = '<div id="target" x-data="{count: 0}"><span x-text="count"></span><b>Old</b></div>'
            const target = document.querySelector('#target')
            Alpine.initTree(target)
            await Alpine.nextTick()
            Alpine.$data(target).count = 7
            await Alpine.nextTick()

            await createRenderer('<div id="target" x-data="{count: 0}"><span x-text="count"></span><b>New</b></div>').renderOuterHtml(target)
            await Alpine.nextTick()

            expect(document.querySelector('#target')).toBe(target)
            expect(target.querySelector('span').textContent).toBe('7')
            expect(target.querySelector('b').textContent).toBe('New')
        })

        test('empty inner HTML clears children without removing the target', async () => {
            document.body.innerHTML = '<div id="target"><p>Old</p></div>'
            await createRenderer('').renderInnerHtml('#target')
            expect(document.querySelector('#target').childNodes.length).toBe(0)
        })

        for (const html of ['', 'text', '<p>One</p><p>Two</p>', 'text<p>One</p>']) {
            test(`rejects invalid outer HTML ${JSON.stringify(html)} without changing the DOM`, async () => {
                document.body.innerHTML = '<div id="target">Old</div>'
                await expect(createRenderer(html).renderOuterHtml('#target')).rejects.toThrow('exactly one root element')
                expect(document.body.innerHTML).toBe('<div id="target">Old</div>')
            })
        }

        test('rejects missing targets', async () => {
            await expect(createRenderer('<p>New</p>').renderInnerHtml('#missing')).rejects.toThrow('HTML target')
        })
    })
}
