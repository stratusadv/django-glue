import {afterEach, describe, expect, test} from "bun:test"
import {Window} from "happy-dom"

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

    test('rejects an already loaded external Alpine runtime', () => {
        const page = createPage()
        page.Alpine = {version: 'external'}

        expect(() => page.eval(bundle)).toThrow('Remove the separate Alpine core script')
        expect(page.Alpine.version).toBe('external')
    })
})
