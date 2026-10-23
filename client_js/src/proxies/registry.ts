import type {GlueProxyClass} from "../runtime/addressRegistry"

const NAMESPACE_TO_PROXY_CLASS: Record<string, GlueProxyClass> = {}

function registerProxyClass(namespace: string, proxyClass: GlueProxyClass): void {
    NAMESPACE_TO_PROXY_CLASS[namespace] = proxyClass
}

function getProxyClass(namespace: string): GlueProxyClass | undefined {
    return NAMESPACE_TO_PROXY_CLASS[namespace]
}

export {
    getProxyClass,
    registerProxyClass,
}
