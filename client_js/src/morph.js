import {morph as alpineMorph} from "./alpine"
import {htmlToFragment} from "./utils"

// A subtree owned by third-party JavaScript (charts, date pickers, editors)
// opts out: the server render knows nothing about the nodes it wrote, so any
// strategy that rebuilds them from server HTML wipes that work.
const IGNORE_ATTRIBUTE = 'data-morph-ignore'

function shouldIgnore(node) {
    return node.nodeType === Node.ELEMENT_NODE && node.hasAttribute(IGNORE_ATTRIBUTE)
}

const MORPH_OPTIONS = {
    updating: (element, toElement, childrenOnly, skip) => {
        if (shouldIgnore(element)) skip()
    },
}

function isSignificant(node) {
    if (node.nodeType === Node.COMMENT_NODE) return false
    if (node.nodeType === Node.TEXT_NODE) return node.textContent.trim() !== ''
    return true
}

function soleElementOf(fragment) {
    const nodes = [...fragment.childNodes].filter(isSignificant)

    if (nodes.length === 1 && nodes[0].nodeType === Node.ELEMENT_NODE) {
        return nodes[0]
    }

    return null
}

// Server-rendered HTML that replaces existing content is morphed rather than
// swapped, because replacement destroys Alpine scopes, focus, caret position
// and any local UI state inside the replaced subtree. Insertion is not
// replacement and stays plain insertion.
//
// Morphing reconciles one element against one element, so it only applies when
// the incoming HTML *is* one element. A multi-node fragment -- a `<style>`
// followed by content, say -- has no single identity to preserve, which makes
// replacement the correct semantic for it rather than a fallback.
function morphElement(element, html) {
    const fragment = htmlToFragment(html)
    const root = soleElementOf(fragment)

    if (root === null) {
        element.replaceWith(fragment)
        return
    }

    alpineMorph(element, root.outerHTML, MORPH_OPTIONS)
}

// Morphs an element's children while leaving the element itself in place. The
// shallow clone reproduces the target's own tag and attributes so the morph
// sees them unchanged and only reconciles what is inside. The container is the
// stable identity here, so any number of children is fine.
function morphChildren(element, html) {
    const shell = element.cloneNode(false)
    shell.innerHTML = html

    alpineMorph(element, shell.outerHTML, MORPH_OPTIONS)
}

export {IGNORE_ATTRIBUTE, morphChildren, morphElement}
