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

        test('a kept child placeholder leaves the live child in place', async () => {
            // happy-dom mis-parses table markup inside <template>; the browser
            // suite checks that a placeholder stays in place inside a table.
            document.body.innerHTML = '<ul id="target"><li>Old</li><li data-glue-address="p[row]">Live</li></ul>'
            const target = document.querySelector('#target')
            const row = target.querySelector('[data-glue-address]')

            await createRenderer(
                '<ul id="target"><li>New</li><template data-glue-keep="p[row]"></template></ul>'
            ).renderOuterHtml(target)

            expect(target.querySelector('[data-glue-address]')).toBe(row)
            expect(row.textContent).toBe('Live')
            expect(target.firstElementChild.textContent).toBe('New')
            expect(target.querySelector('template')).toBeNull()
        })

        test('a kept child keeps the nodes Alpine generated inside it', async () => {
            document.body.innerHTML = '<div id="target"><div data-glue-address="p[row]" x-data="{items: [1, 2]}"><template x-for="item in items"><b x-text="item"></b></template></div></div>'
            const target = document.querySelector('#target')
            Alpine.initTree(target)
            await Alpine.nextTick()

            await createRenderer('<div id="target"><template data-glue-keep="p[row]"></template></div>').renderOuterHtml(target)
            await Alpine.nextTick()

            expect([...target.querySelectorAll('b')].map(node => node.textContent)).toEqual(['1', '2'])
        })

        test('a placeholder for a child that is gone is dropped', async () => {
            document.body.innerHTML = '<div id="target"><p>Old</p></div>'

            await createRenderer('<div id="target"><template data-glue-keep="p[gone]"></template><p>New</p></div>').renderOuterHtml('#target')

            expect(document.querySelector('#target').innerHTML).toBe('<p>New</p>')
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
