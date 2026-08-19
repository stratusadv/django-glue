import {resolveElement, htmlToFragment} from "./utils"

// Wraps a server-rendered HTML string with the same render*Html API as
// GlueView/GlueTemplateProxy, so a `@Glue.attr` method that returns a
// GlueTemplateResponse (see django_glue.response.GlueTemplateResponse) can
// be used the same way on the client:
//
//     const result = await Glue.namespace.proxyName.some_custom_thing()
//     await result.renderInnerHtml('#target')
//
// Unlike GlueView/GlueTemplateProxy, `html` here is already known -- the
// attribute call already happened by the time you have this object -- so
// there's no per-call fetch to share with them. These methods stay async
// anyway, purely so callers can `await` either kind of result the same way.
class GlueHtmlResult {
    constructor(html) {
        this.html = html
    }

    toString() {
        return this.html
    }

    async renderInnerHtml(target) {
        resolveElement(target).replaceChildren(htmlToFragment(this.html))
        return this.html
    }

    async renderOuterHtml(target) {
        resolveElement(target).replaceWith(htmlToFragment(this.html))
        return this.html
    }

    async _renderInsertAdjacentHtml(target, position) {
        const element = resolveElement(target)
        const fragment = htmlToFragment(this.html)

        if (position === 'beforebegin') {
            element.before(fragment)
        } else if (position === 'afterbegin') {
            element.prepend(fragment)
        } else if (position === 'beforeend') {
            element.append(fragment)
        } else if (position === 'afterend') {
            element.after(fragment)
        } else {
            throw new Error(`Invalid insert position: ${position}`)
        }

        return this.html
    }

    async renderInsertAdjacentHtmlBeforeBegin(target) {
        return await this._renderInsertAdjacentHtml(target, 'beforebegin')
    }

    async renderInsertAdjacentHtmlAfterBegin(target) {
        return await this._renderInsertAdjacentHtml(target, 'afterbegin')
    }

    async renderInsertAdjacentHtmlBeforeEnd(target) {
        return await this._renderInsertAdjacentHtml(target, 'beforeend')
    }

    async renderInsertAdjacentHtmlAfterEnd(target) {
        return await this._renderInsertAdjacentHtml(target, 'afterend')
    }
}

export default GlueHtmlResult
