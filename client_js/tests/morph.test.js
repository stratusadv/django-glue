import {beforeEach, describe, expect, test} from "bun:test"
import {IGNORE_ATTRIBUTE, morphComponentRoot} from "../src/morph"
import GlueComponentHtmlResult from "../src/componentHtmlResult"

describe('Morphing a component root', () => {
    beforeEach(() => {
        document.body.innerHTML = ''
    })

    test('content updates while the root element itself survives', () => {
        document.body.innerHTML = '<div data-glue="card_a1"><span>Old</span></div>'
        const element = document.querySelector('[data-glue="card_a1"]')

        morphComponentRoot(element, '<div data-glue="card_a1"><span>New</span></div>')

        // The point of morphing: the node survives, so an Alpine scope, focus,
        // and caret position attached to it survive with it.
        expect(document.querySelector('[data-glue="card_a1"]')).toBe(element)
        expect(element.textContent).toBe('New')
    })

    test('an unchanged child keeps its node identity', () => {
        document.body.innerHTML =
            '<ul data-glue="list_a1"><li id="a">A</li><li id="b">B</li></ul>'
        const element = document.querySelector('[data-glue="list_a1"]')
        const unchanged = document.getElementById('a')

        morphComponentRoot(
            element,
            '<ul data-glue="list_a1"><li id="a">A</li><li id="b">B changed</li></ul>',
        )

        expect(document.getElementById('a')).toBe(unchanged)
        expect(document.getElementById('b').textContent).toBe('B changed')
    })

    test('a subtree marked data-morph-ignore is left alone', () => {
        document.body.innerHTML =
            `<div data-glue="card_a1"><div id="widget" ${IGNORE_ATTRIBUTE}>third-party</div></div>`
        const element = document.querySelector('[data-glue="card_a1"]')
        const widget = document.getElementById('widget')
        widget.dataset.painted = 'yes'

        morphComponentRoot(
            element,
            `<div data-glue="card_a1"><div id="widget" ${IGNORE_ATTRIBUTE}></div></div>`,
        )

        expect(document.getElementById('widget')).toBe(widget)
        expect(widget.dataset.painted).toBe('yes')
        expect(widget.textContent).toBe('third-party')
    })

    test('unrelated siblings are untouched', () => {
        document.body.innerHTML =
            '<div data-glue="first_a1">First</div><div id="second">Second</div>'
        const first = document.querySelector('[data-glue="first_a1"]')
        const second = document.getElementById('second')

        morphComponentRoot(first, '<div data-glue="first_a1">Changed</div>')

        expect(document.getElementById('second')).toBe(second)
        expect(first.textContent).toBe('Changed')
        expect(second.textContent).toBe('Second')
    })

    test('a child keeps its node when its address is unchanged', () => {
        document.body.innerHTML =
            '<div data-glue="week_a1"><div data-glue="day_mon">Mon</div></div>'
        const element = document.querySelector('[data-glue="week_a1"]')
        const monday = document.querySelector('[data-glue="day_mon"]')

        morphComponentRoot(
            element,
            '<div data-glue="week_a1"><div data-glue="day_mon">Mon updated</div></div>',
        )

        expect(document.querySelector('[data-glue="day_mon"]')).toBe(monday)
        expect(monday.textContent).toBe('Mon updated')
    })

    test('a child whose address changed is replaced, not recycled', () => {
        // A dashboard moving to the next week: same position, different
        // component. Patching the old node into the new component would carry
        // over whatever is bound to that node but absent from the server HTML.
        document.body.innerHTML =
            '<div data-glue="week_a1"><div data-glue="day_oct_02">Oct 2</div></div>'
        const element = document.querySelector('[data-glue="week_a1"]')
        const oldDay = document.querySelector('[data-glue="day_oct_02"]')

        morphComponentRoot(
            element,
            '<div data-glue="week_a1"><div data-glue="day_oct_09">Oct 9</div></div>',
        )

        expect(document.querySelector('[data-glue="day_oct_02"]')).toBeNull()
        expect(document.querySelector('[data-glue="day_oct_09"]')).not.toBe(oldDay)
        expect(element.textContent).toBe('Oct 9')
    })

    test('the key attribute still resolves for ordinary markup', () => {
        // Supplying `key` replaces Alpine's default resolver, so authored keys
        // have to keep working.
        document.body.innerHTML =
            '<ul data-glue="list_a1"><li key="b">B</li></ul>'
        const element = document.querySelector('[data-glue="list_a1"]')
        const itemB = document.querySelector('[key="b"]')

        morphComponentRoot(
            element,
            '<ul data-glue="list_a1"><li key="a">A</li><li key="b">B</li></ul>',
        )

        expect(document.querySelector('[key="b"]')).toBe(itemB)
        expect(element.textContent).toBe('AB')
    })
})

describe('Applying a component render result', () => {
    beforeEach(() => {
        document.body.innerHTML = ''
    })

    test('it finds its own root, so no target is supplied', () => {
        document.body.innerHTML =
            '<div><div data-glue="day_a1"><span>Old</span></div></div>'
        const element = document.querySelector('[data-glue="day_a1"]')

        const html = new GlueComponentHtmlResult(
            '<div data-glue="day_a1"><span>New</span></div>',
            'day_a1',
        ).apply()

        expect(document.querySelector('[data-glue="day_a1"]')).toBe(element)
        expect(element.textContent).toBe('New')
        expect(html).toContain('New')
    })

    test('a missing root is a named error, not a silent no-op', () => {
        expect(
            () => new GlueComponentHtmlResult('<div></div>', 'gone_a1').apply(),
        ).toThrow(/gone_a1/)
    })

    test('it stringifies to its HTML', () => {
        const result = new GlueComponentHtmlResult('<div>x</div>', 'a1')

        expect(String(result)).toBe('<div>x</div>')
    })
})
