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
