import {definePath} from "./attributeMaterializer"

class GlueChildBinder {
    constructor(registry) {
        this.registry = registry
    }

    refresh(record) {
        if (!record.proxy) return
        const paths = new Set([
            ...Object.keys(record.staticData.children || {}),
            ...Object.keys(record.policy.children || {}),
        ])
        paths.forEach(path => {
            definePath(record.proxy, path, {
                get: () => {
                    const childAddress = record.policy.children?.[path]
                    if (!childAddress) return null
                    const child = this.registry.getProxy(childAddress)
                    if (child && child._owner !== record.proxy) child._owner = record.proxy
                    return child
                },
                enumerable: true,
            })
        })
    }
}

export default GlueChildBinder
