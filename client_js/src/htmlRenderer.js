import {morph} from "./alpine"
import {GlueProxyError} from "./errors"

function htmlToFragment(html) {
    const template = document.createElement('template')
    template.innerHTML = html
    return template.content
}

function resolveElement(target) {
    return typeof target === 'string' ? document.querySelector(target) : target
}

const HtmlRenderer = (Base = class {}) => class extends Base {
    async renderInnerHtml(target, payload = {}) {
        const element = this._resolveHtmlTarget(target)
        const html = await this._getHtml(payload)
        const next = element.cloneNode(false)
        next.innerHTML = html
        this._morphHtml(element, next, true)
        return html
    }

    async renderOuterHtml(target, payload = {}) {
        const element = this._resolveHtmlTarget(target)
        const html = await this._getHtml(payload)
        const fragment = htmlToFragment(html)
        const nodes = [...fragment.childNodes].filter(node =>
            node.nodeType !== Node.COMMENT_NODE
            && !(node.nodeType === Node.TEXT_NODE && !node.textContent.trim())
        )
        if (nodes.length !== 1 || nodes[0].nodeType !== Node.ELEMENT_NODE) {
            throw new GlueProxyError('renderOuterHtml requires exactly one root element.')
        }
        this._morphHtml(element, nodes[0])
        return html
    }

    _morphHtml(element, next, inner = false) {
        morph(element, next, {
            key: node => node.getAttribute?.('key') || node.id,
            updating(node, to, childrenOnly, skip) {
                if (node.hasAttribute?.('data-morph-ignore')) return skip()
                if (inner && node === element) childrenOnly()
            },
        })
    }

    _resolveHtmlTarget(target) {
        const element = resolveElement(target)
        if (!element || element.nodeType !== Node.ELEMENT_NODE) {
            throw new GlueProxyError(`HTML target was not found or is not an element: ${target}`)
        }
        return element
    }

    async _renderInsertAdjacentHtml(target, position, payload = {}) {
        if (!['beforebegin', 'afterbegin', 'beforeend', 'afterend'].includes(position)) {
            throw new GlueProxyError(`Invalid insert position: ${position}`)
        }
        const element = this._resolveHtmlTarget(target)
        const html = await this._getHtml(payload)
        const fragment = htmlToFragment(html)
        if (position === 'beforebegin') element.before(fragment)
        else if (position === 'afterbegin') element.prepend(fragment)
        else if (position === 'beforeend') element.append(fragment)
        else element.after(fragment)
        return html
    }

    async renderInsertAdjacentHtmlBeforeBegin(target, payload = {}) {
        return this._renderInsertAdjacentHtml(target, 'beforebegin', payload)
    }

    async renderInsertAdjacentHtmlAfterBegin(target, payload = {}) {
        return this._renderInsertAdjacentHtml(target, 'afterbegin', payload)
    }

    async renderInsertAdjacentHtmlBeforeEnd(target, payload = {}) {
        return this._renderInsertAdjacentHtml(target, 'beforeend', payload)
    }

    async renderInsertAdjacentHtmlAfterEnd(target, payload = {}) {
        return this._renderInsertAdjacentHtml(target, 'afterend', payload)
    }
}

class HtmlResult extends HtmlRenderer() {
    constructor(html) {
        super()
        this.html = html
    }

    toString() {
        return this.html
    }

    async _getHtml() {
        return this.html
    }
}

function htmlResultFromResponse(data, client) {
    client?.loadManifests(data?.manifest_list || [])
    return new HtmlResult(data?.html || '')
}

export {htmlResultFromResponse}
export default HtmlRenderer
