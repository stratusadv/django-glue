import {afterEach, describe, expect, test} from "bun:test"
import {Window} from "happy-dom"
import {createEntry} from "./testUtils"

const bundle = await Bun.file('django_glue/static/django_glue/js/django_glue.js').text()
const windows = []

function createPage() {
    const page = new Window({url: 'http://localhost/'})
    windows.push(page)
    Object.defineProperty(page.document, 'readyState', {value: 'loading', configurable: true})
    return page
}

afterEach(async () => {
    await Promise.all(windows.splice(0).map(page => page.happyDOM.close()))
})

describe('bundled Alpine startup', () => {
    test('inline Glue setup and plugins register before Alpine mounts the page once', async () => {
        const page = createPage()
        page.eval(bundle)
        page.eval(`
            window.Glue = new GlueClient({objects: []})
            Glue.onMessage(() => {})
            window.mounts = 0
            document.addEventListener('alpine:init', () => {
                Alpine.store('theme', {name: 'dark'})
                Alpine.plugin(alpine => alpine.magic('portal', () => 'ready'))
            })
        `)
        page.document.body.innerHTML = '<div x-data x-init="window.mounts++"><span x-text="$store.theme.name + \':\' + $portal"></span></div>'

        expect(page.mounts).toBe(0)
        expect(typeof page.Alpine.morph).toBe('function')
        page.document.dispatchEvent(new page.Event('DOMContentLoaded'))
        page.dispatchEvent(new page.Event('load'))
        await page.Alpine.nextTick()

        expect(page.mounts).toBe(1)
        expect(page.document.querySelector('span').textContent).toBe('dark:ready')
    })

    test('the bundle starts when loaded after the page is ready', async () => {
        const page = createPage()
        Object.defineProperty(page.document, 'readyState', {value: 'complete', configurable: true})
        page.document.body.innerHTML = '<div x-data="{name: \'ready\'}" x-text="name"></div>'
        page.eval(bundle)
        await page.happyDOM.waitUntilComplete()

        expect(page.document.querySelector('div').textContent).toBe('ready')
    })

    test('a nested component root inherits its ancestors x-data under its own component scope', async () => {
        const page = createPage()
        page.eval(bundle)
        const component = address => createEntry({
            policy: {name: address, namespace: 'component', address, attributes: [], state_snapshot: {}},
            static_data: {fields: {}, callables: {}},
        })
        page.document.body.innerHTML = `
            <div data-glue-address="tally#test" x-data="{categories: ['Software']}">
                <div data-glue-address="tally#test[card]" x-data="{open: false}">
                    <span x-text="[categories[0], component.$el.getAttribute('data-glue-address'), open].join(':')"></span>
                </div>
            </div>`
        page.document.querySelector('[data-glue-address="tally#test"]')
            .setAttribute('data-glue-objects', JSON.stringify([component('tally#test')]))
        page.document.querySelector('[data-glue-address="tally#test[card]"]')
            .setAttribute('data-glue-objects', JSON.stringify([component('tally#test[card]')]))
        page.eval('window.Glue = new GlueClient({objects: []})')

        page.document.dispatchEvent(new page.Event('DOMContentLoaded'))
        await page.Alpine.nextTick()
        page.Glue.registerComponentsFromDom()
        const card = page.document.querySelector('[data-glue-address="tally#test[card]"]')
        const scopes = card._x_dataStack.length
        page.Glue.registerComponentsFromDom()

        expect(page.document.querySelector('span').textContent).toBe('Software:tally#test[card]:false')
        expect(card._x_dataStack.length).toBe(scopes)
    })

    test('rejects an already loaded external Alpine runtime', () => {
        const page = createPage()
        page.Alpine = {version: 'external'}

        expect(() => page.eval(bundle)).toThrow('Remove the separate Alpine core script')
        expect(page.Alpine.version).toBe('external')
    })
})
