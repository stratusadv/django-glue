const NAMESPACE_TO_PROXY_CLASS = {}

function registerProxyClass(namespace, proxyClass) {
    NAMESPACE_TO_PROXY_CLASS[namespace] = proxyClass
}

function getProxyClass(namespace) {
    return NAMESPACE_TO_PROXY_CLASS[namespace]
}

export {
    getProxyClass,
    registerProxyClass,
}
