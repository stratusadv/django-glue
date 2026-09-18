import {morph as alpineMorph} from "./alpine"

// A subtree owned by third-party JavaScript (charts, date pickers, editors)
// opts out: the server render knows nothing about the nodes it wrote, so any
// strategy that rebuilds them from server HTML wipes that work.
const IGNORE_ATTRIBUTE = 'data-morph-ignore'

// The attribute a component's root carries, and the namespace its proxy
// registers under. Together they let the client find a component's DOM root
// and decide whether it is still live.
const ROOT_ATTRIBUTE = 'data-glue'
const COMPONENT_NAMESPACE = 'component'

function shouldIgnore(node) {
    return node.nodeType === Node.ELEMENT_NODE && node.hasAttribute(IGNORE_ATTRIBUTE)
}

// Morph boundaries are component boundaries (component-system.md §6). A
// component's root is guaranteed to be a single element and carries data-glue,
// so there is exactly one node to reconcile against and no fragment case to
// handle. Generic HTML results and Glue.view fragments have no address and are
// replaced, not morphed.
//
// Morphing is what preserves Alpine scopes, focus, caret position and local UI
// state across a re-render; replacement destroys all of it.
function morphComponentRoot(element, html) {
    alpineMorph(element, html, {
        updating: (current, incoming, childrenOnly, skip) => {
            if (shouldIgnore(current)) skip()
        },
    })
}

function componentRoot(name) {
    return document.querySelector(`[${ROOT_ATTRIBUTE}="${name}"]`)
}

export {
    COMPONENT_NAMESPACE,
    IGNORE_ATTRIBUTE,
    ROOT_ATTRIBUTE,
    componentRoot,
    morphComponentRoot,
}
