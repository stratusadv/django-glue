import Alpine from "alpinejs"
import morphPlugin from "@alpinejs/morph"
import {GlueAlpineError} from "./errors"

Alpine.plugin(morphPlugin)
Alpine.magic('glue', element => globalThis.Glue?.from(element) || null)

// Alpine runs directive handlers after walking the whole tree, parents first.
// Ordered before x-data, this attaches a component root's `component` scope
// after its ancestors' x-data exist, so the root inherits them, and before its
// own x-data, which layers on top.
Alpine.directive('glue-component', element => {
    const proxy = globalThis.Glue?.from(element)
    if (proxy) Alpine.addScopeToNode(element, {component: proxy})
}).before('data')

let installed = false
let started = false

function installAlpine() {
    if (globalThis.Alpine && globalThis.Alpine !== Alpine) {
        throw new GlueAlpineError('Glue bundles Alpine.js. Remove the separate Alpine core script from this page.')
    }
    if (installed) return
    installed = true
    globalThis.Alpine = Alpine

    const start = () => {
        if (started) return
        if (globalThis.Alpine !== Alpine) {
            throw new GlueAlpineError('Another script replaced Glue\'s Alpine.js. Remove the separate Alpine core script.')
        }
        started = true
        Alpine.start()
    }

    // Deferred plugins and inline alpine:init handlers must register first.
    if (document.readyState === 'complete') {
        queueMicrotask(start)
    } else {
        document.addEventListener('DOMContentLoaded', start, {once: true})
        globalThis.addEventListener('load', start, {once: true})
    }
}

function reactive(object) {
    if (object === null || typeof object !== 'object') return object
    return Alpine.reactive(object)
}

function morph(element, html, options = {}) {
    return Alpine.morph(element, html, options)
}

// A root Alpine has not initialized yet gets its scope from the directive
// above. One Alpine already initialized gets it here, once.
function addComponentScope(element, proxy) {
    if (!element._x_marker) {
        element.setAttribute('x-glue-component', '')
        return
    }
    if (element._x_dataStack?.some(scope => scope.component === proxy)) return
    Alpine.addScopeToNode(element, {component: proxy})
}

export {installAlpine, reactive, morph, addComponentScope}
