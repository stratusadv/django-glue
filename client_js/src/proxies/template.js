import BaseGlueProxy from "./base";

/**
 * Proxy for Django templates. Renders templates server-side with dynamic context
 * data and provides the same DOM injection methods as {@link GlueView}.
 */
class GlueTemplateProxy extends BaseGlueProxy {
    /** @type {string} */
    static name = 'template'

    /**
     * @param {Object} options - Constructor options.
     * @param {GlueHttp} options.http - The HTTP client instance.
     * @param {string} options.name - The unique name of this proxy.
     * @param {Object} options.policy - Serialized proxy policy from the server.
     * @param {Object} [options.state] - Proxy state.
     * @param {Object} [options.sharedPayload={}] - Payload merged into every request.
     */
    constructor({http, name, policy, state = null, sharedPayload = {}}) {
        super({http, name, policy, state});

        /** @type {Object} */
        this._sharedPayload = sharedPayload;
    }

    /**
     * Fetch rendered HTML from the server by calling the render_html bound attribute.
     * Merges sharedPayload with the per-call payload.
     * @param {Object} [payload] - Additional context data merged with sharedPayload.
     * @returns {Promise<string>} Rendered HTML string.
     * @private
     */
    async _renderHtml(payload = {}) {
        const mergedPayload = {
            ...this._sharedPayload,
            ...payload,
        };

        const response = await this.render_html(mergedPayload);

        return response.html;
    }

    /**
     * Replace the inner HTML of a target element with rendered template HTML.
     * @param {HTMLElement} targetElement - The DOM element to update.
     * @param {Object} [payload] - Additional context data.
     */
    async renderInnerHtml(targetElement, payload = {}) {
        targetElement.innerHTML = await this._renderHtml(payload);
    }

    /**
     * Insert rendered template HTML adjacent to a target element.
     * @param {HTMLElement} targetElement - The DOM element.
     * @param {string} position - Insert position ('beforeend', 'afterend', 'beforebegin', 'afterbegin').
     * @param {Object} [payload] - Additional context data.
     * @private
     */
    async _renderInsertAdjacentHtml(targetElement, position, payload = {}) {
        const html = await this._renderHtml(payload);
        targetElement.insertAdjacentHTML(position, html);
    }

    /**
     * Insert rendered template HTML at the end of the target element's children.
     * @param {HTMLElement} targetElement - The DOM element.
     * @param {Object} [payload] - Additional context data.
     */
    async renderInsertAdjacentHtmlBeforeEnd(targetElement, payload = {}) {
        await this._renderInsertAdjacentHtml(targetElement, 'beforeend', payload);
    }

    /**
     * Insert rendered template HTML after the target element.
     * @param {HTMLElement} targetElement - The DOM element.
     * @param {Object} [payload] - Additional context data.
     */
    async renderInsertAdjacentHtmlAfterEnd(targetElement, payload = {}) {
        await this._renderInsertAdjacentHtml(targetElement, 'afterend', payload);
    }

    /**
     * Insert rendered template HTML before the target element.
     * @param {HTMLElement} targetElement - The DOM element.
     * @param {Object} [payload] - Additional context data.
     */
    async renderInsertAdjacentHtmlBeforeBegin(targetElement, payload = {}) {
        await this._renderInsertAdjacentHtml(targetElement, 'beforebegin', payload);
    }

    /**
     * Insert rendered template HTML at the beginning of the target element's children.
     * @param {HTMLElement} targetElement - The DOM element.
     * @param {Object} [payload] - Additional context data.
     */
    async renderInsertAdjacentHtmlAfterBegin(targetElement, payload = {}) {
        await this._renderInsertAdjacentHtml(targetElement, 'afterbegin', payload);
    }

    /**
     * Replace the target element entirely (outer HTML) with rendered template HTML.
     * @param {HTMLElement} targetElement - The DOM element to replace.
     * @param {Object} [payload] - Additional context data.
     */
    async renderOuterHtml(targetElement, payload = {}) {
        targetElement.outerHTML = await this._renderHtml(payload);
    }
}

export default GlueTemplateProxy;
