import {morph as alpineMorph} from "./alpine"

// A subtree owned by third-party JavaScript (charts, date pickers, editors)
// opts out: the server render knows nothing about the nodes it wrote, so any
// strategy that rebuilds them from server HTML wipes that work.
const IGNORE_ATTRIBUTE = 'data-morph-ignore'

// The attribute a component's root carries, and the namespace its proxy
// registers under. Together they let the client find a component's DOM root
// and decide whether it is still live.
const ROOT_ATTRIBUTE = 'data-glue'
const MANIFEST_ATTRIBUTE = 'data-glue-manifest'
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
        // Addresses supply the node keys (spec.md §8). Without this, children
        // are matched positionally: a dashboard moving to the next week would
        // patch each day card's node into the *next* week's component rather
        // than replacing it, recycling whatever is bound to that node but not
        // described by the server HTML. A child whose data-glue changed is a
        // different component, so it is replaced.
        //
        // Falls back to the `key` attribute because passing this option
        // replaces Alpine's default resolver outright, and authored keys on
        // ordinary markup have to keep working.
        key: node => node.getAttribute(ROOT_ATTRIBUTE) || node.getAttribute('key'),
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
    MANIFEST_ATTRIBUTE,
    ROOT_ATTRIBUTE,
    componentRoot,
    morphComponentRoot,
}
