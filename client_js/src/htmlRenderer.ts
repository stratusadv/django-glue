import {morph} from "./alpine"
import type GlueClient from "./client"
import {GlueProxyError} from "./errors"
import type {GlueObjectEntry} from "./wire"

type GlueHtmlTarget = string | Element

type GlueInsertPosition = 'beforebegin' | 'afterbegin' | 'beforeend' | 'afterend'

// A mixin's base constructor has to take `any[]`: TypeScript accepts no other
// signature for one.
type GlueConstructor = new (...args: any[]) => object

function htmlToFragment(html: string): DocumentFragment {
    const template = document.createElement('template')
    template.innerHTML = html
    return template.content
}

function resolveElement(target: GlueHtmlTarget): Element | null {
    return typeof target === 'string' ? document.querySelector(target) : target
}

const HtmlRenderer = <TBase extends GlueConstructor>(Base: TBase = class {} as TBase) => {
    abstract class HtmlRendering extends Base {
        declare _client: GlueClient | null | undefined

        // The HTML to place, or null when there is none to render.
        abstract _getHtml(payload?: Record<string, unknown>): Promise<string | null>

        async renderInnerHtml(target: GlueHtmlTarget, payload: Record<string, unknown> = {}): Promise<string | null> {
            const element = this._resolveHtmlTarget(target)
            const html = await this._getHtml(payload)
            if (html === null) return null
            const next = element.cloneNode(false) as Element
            next.innerHTML = html
            this._morphHtml(element, next, true)
            return html
        }

        async renderOuterHtml(target: GlueHtmlTarget, payload: Record<string, unknown> = {}): Promise<string | null> {
            const element = this._resolveHtmlTarget(target)
            const html = await this._getHtml(payload)
            if (html === null) return null
            const fragment = htmlToFragment(html)
            const nodes = [...fragment.childNodes].filter(node =>
                node.nodeType !== Node.COMMENT_NODE
                && !(node.nodeType === Node.TEXT_NODE && !node.textContent!.trim())
            )
            if (nodes.length !== 1 || nodes[0].nodeType !== Node.ELEMENT_NODE) {
                throw new GlueProxyError('renderOuterHtml requires exactly one root element.')
            }
            this._morphHtml(element, nodes[0] as Element)
            return html
        }

        _morphHtml(element: Element, next: Element, inner = false): void {
            const client = this._client
            const previousNodes = [
                ...(element.matches?.('[data-glue-address]') ? [element] : []),
                ...element.querySelectorAll('[data-glue-address]'),
            ]
            const previousAddresses = client
                ? previousNodes.map(node => node.getAttribute('data-glue-address')!)
                : []
            // A child the server kept arrives as a placeholder (ADR 025). Put an
            // empty copy of the live child's element there, so the morph pairs the
            // two, and mark it so the morph leaves the live child untouched. A
            // deep copy would carry nodes Alpine generated, such as x-for items.
            next.querySelectorAll('template[data-glue-keep]').forEach(placeholder => {
                const address = placeholder.getAttribute('data-glue-keep')
                const live = previousNodes.find(node => node.getAttribute('data-glue-address') === address)
                if (!live) return placeholder.remove()
                const shell = live.cloneNode(false) as Element & {_glueKeep?: boolean}
                shell._glueKeep = true
                placeholder.replaceWith(shell)
            })
            morph(element, next, {
                key: (node: Element) => node.getAttribute?.('data-glue-address') || node.getAttribute?.('key') || node.id,
                updating(node: Element, to: (Element & {_glueKeep?: boolean}) | undefined, childrenOnly: () => void, skip: () => void) {
                    if (to?._glueKeep || node.hasAttribute?.('data-morph-ignore')) return skip()
                    if (inner && node === element) childrenOnly()
                },
            })
            client?.registerComponentsFromDom(document)
            previousAddresses.forEach(address => {
                if (![...document.querySelectorAll('[data-glue-address]')].some(
                    node => node.getAttribute('data-glue-address') === address
                )) client!._registry.dispose(address)
            })
        }

        _resolveHtmlTarget(target: GlueHtmlTarget): Element {
            const element = resolveElement(target)
            if (!element || element.nodeType !== Node.ELEMENT_NODE) {
                throw new GlueProxyError(`HTML target was not found or is not an element: ${target}`)
            }
            return element
        }

        async _renderInsertAdjacentHtml(
            target: GlueHtmlTarget,
            position: GlueInsertPosition,
            payload: Record<string, unknown> = {},
        ): Promise<string | null> {
            if (!['beforebegin', 'afterbegin', 'beforeend', 'afterend'].includes(position)) {
                throw new GlueProxyError(`Invalid insert position: ${position}`)
            }
            const element = this._resolveHtmlTarget(target)
            const html = await this._getHtml(payload)
            if (html === null) return null
            const fragment = htmlToFragment(html)
            if (position === 'beforebegin') element.before(fragment)
            else if (position === 'afterbegin') element.prepend(fragment)
            else if (position === 'beforeend') element.append(fragment)
            else element.after(fragment)
            this._client?.registerComponentsFromDom(document)
            return html
        }

        async renderInsertAdjacentHtmlBeforeBegin(target: GlueHtmlTarget, payload: Record<string, unknown> = {}) {
            return this._renderInsertAdjacentHtml(target, 'beforebegin', payload)
        }

        async renderInsertAdjacentHtmlAfterBegin(target: GlueHtmlTarget, payload: Record<string, unknown> = {}) {
            return this._renderInsertAdjacentHtml(target, 'afterbegin', payload)
        }

        async renderInsertAdjacentHtmlBeforeEnd(target: GlueHtmlTarget, payload: Record<string, unknown> = {}) {
            return this._renderInsertAdjacentHtml(target, 'beforeend', payload)
        }

        async renderInsertAdjacentHtmlAfterEnd(target: GlueHtmlTarget, payload: Record<string, unknown> = {}) {
            return this._renderInsertAdjacentHtml(target, 'afterend', payload)
        }
    }

    return HtmlRendering
}

class HtmlResult extends HtmlRenderer() {
    html: string

    constructor(html: string, client: GlueClient | null = null) {
        super()
        this.html = html
        this._client = client
    }

    toString(): string {
        return this.html
    }

    async _getHtml(): Promise<string> {
        return this.html
    }
}

function htmlResultFromResponse(
    data: {html?: string, objects?: GlueObjectEntry[]} | null | undefined,
    client: GlueClient | null | undefined,
): HtmlResult {
    client?.loadObjects(data?.objects || [])
    return new HtmlResult(data?.html || '', client)
}

export type {GlueHtmlTarget, HtmlResult}
export {htmlResultFromResponse, htmlToFragment}
export default HtmlRenderer
