import {definePath} from "./attributeMaterializer"

// A child's address is derived from its owner's address (state-model.md §10):
// `owner.path`, `owner[key]`, or `owner["t…"]`. A record that binds an address
// it did not derive only holds a reference, which never makes it an owner
// (§4), so it neither claims the child nor disposes it when the reference goes.
export function isOwnedBy(address, ownerAddress) {
    return address.startsWith(`${ownerAddress}.`) || address.startsWith(`${ownerAddress}[`)
}

class GlueChildBinder {
    constructor(registry) {
        this.registry = registry
    }

    refresh(record) {
        if (!record.proxy) return
        record.displacedChildren = this._displacedAddresses(record)
        const paths = new Set([
            ...Object.keys(record.staticData.children || {}),
            ...Object.keys(record.policy.children || {}),
        ])
        paths.forEach(path => {
            const childAddress = record.policy.children?.[path]
            if (childAddress) {
                const child = this.registry.getProxy(childAddress)
                if (child) this._link(child, record, path)
            }
            definePath(record.proxy, path, {
                get: () => {
                    const childAddress = record.policy.children?.[path]
                    if (!childAddress) return null
                    const child = this.registry.getProxy(childAddress)
                    if (child) this._link(child, record, path)
                    return child
                },
                enumerable: true,
            })
        })
        record.boundChildren = {...(record.policy.children || {})}
    }

    _displacedAddresses(record) {
        const current = record.policy.children || {}
        const displaced = []
        Object.entries(record.boundChildren || {}).forEach(([path, oldAddress]) => {
            if (current[path] !== oldAddress && isOwnedBy(oldAddress, record.address)) {
                displaced.push(oldAddress)
            }
        })
        return displaced
    }

    _link(child, record, path) {
        if (!isOwnedBy(child._record.address, record.address)) return
        if (child._owner !== record.proxy) child._owner = record.proxy
        child._record.owner = {address: record.address, path}
    }
}

export default GlueChildBinder
