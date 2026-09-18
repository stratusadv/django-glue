import {beforeEach, describe, expect, test} from "bun:test"
import {IGNORE_ATTRIBUTE, morphChildren, morphElement} from "../src/morph"

describe('Morphing replaced HTML', () => {
    beforeEach(() => {
        document.body.innerHTML = ''
    })

    test('morphElement updates content while preserving the element itself', () => {
        document.body.innerHTML = '<div id="card"><span>Old</span></div>'
        const element = document.getElementById('card')

        morphElement(element, '<div id="card"><span>New</span></div>')

        // The point of morphing: the node survives, so an Alpine scope, focus,
        // and caret position attached to it survive with it.
        expect(document.getElementById('card')).toBe(element)
        expect(element.textContent).toBe('New')
    })

    test('morphChildren updates children while preserving the container', () => {
        document.body.innerHTML = '<div id="list" class="a"><span>Old</span></div>'
        const element = document.getElementById('list')

        morphChildren(element, '<span>New</span>')

        expect(document.getElementById('list')).toBe(element)
        expect(element.getAttribute('class')).toBe('a')
        expect(element.textContent).toBe('New')
    })

    test('morphChildren preserves an unchanged child node', () => {
        document.body.innerHTML =
            '<ul id="list"><li id="a">A</li><li id="b">B</li></ul>'
        const element = document.getElementById('list')
        const unchanged = document.getElementById('a')

        morphChildren(element, '<li id="a">A</li><li id="b">B changed</li>')

        expect(document.getElementById('a')).toBe(unchanged)
        expect(document.getElementById('b').textContent).toBe('B changed')
    })

    test('morphChildren accepts several top-level children', () => {
        document.body.innerHTML = '<div id="list"><span>Old</span></div>'
        const element = document.getElementById('list')

        morphChildren(element, '<span>One</span><span>Two</span>')

        expect(element.children).toHaveLength(2)
        expect(element.textContent).toBe('OneTwo')
    })

    test('a subtree marked data-morph-ignore is left alone', () => {
        document.body.innerHTML =
            `<div id="card"><div id="widget" ${IGNORE_ATTRIBUTE}>third-party</div></div>`
        const element = document.getElementById('card')
        const widget = document.getElementById('widget')
        widget.dataset.painted = 'yes'

        morphElement(
            element,
            `<div id="card"><div id="widget" ${IGNORE_ATTRIBUTE}></div></div>`,
        )

        expect(document.getElementById('widget')).toBe(widget)
        expect(widget.dataset.painted).toBe('yes')
        expect(widget.textContent).toBe('third-party')
    })

    test('a multi-node fragment is replaced, since it has no single identity', () => {
        // A Glue.view fragment often opens with a <style> before its content.
        // Morphing would reconcile into the first element and drop the rest.
        document.body.innerHTML = '<div id="host"><div id="slot"></div></div>'
        const host = document.getElementById('host')

        morphElement(
            document.getElementById('slot'),
            '<style>.a{color:red}</style><div class="content">Body</div>',
        )

        expect(host.querySelector('style')).not.toBeNull()
        expect(host.querySelector('.content').textContent).toBe('Body')
        expect(document.getElementById('slot')).toBeNull()
    })

    test('surrounding whitespace does not make a single root look multi-node', () => {
        document.body.innerHTML = '<div id="card">Old</div>'
        const element = document.getElementById('card')

        morphElement(element, '\n  <div id="card">New</div>\n')

        expect(document.getElementById('card')).toBe(element)
        expect(element.textContent).toBe('New')
    })

    test('unrelated siblings are untouched', () => {
        document.body.innerHTML =
            '<div id="first">First</div><div id="second">Second</div>'
        const first = document.getElementById('first')
        const second = document.getElementById('second')

        morphElement(first, '<div id="first">Changed</div>')

        expect(document.getElementById('second')).toBe(second)
        expect(first.textContent).toBe('Changed')
        expect(second.textContent).toBe('Second')
    })
})
