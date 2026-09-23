import Alpine from "alpinejs"
import morphPlugin from "@alpinejs/morph"
import {GlueAlpineError} from "./errors"

Alpine.plugin(morphPlugin)
Alpine.magic('glue', element => globalThis.Glue?.from(element) || null)

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

function addScopeToNode(element, scope) {
    Alpine.addScopeToNode(element, scope)
}

export {installAlpine, reactive, morph, addScopeToNode}
