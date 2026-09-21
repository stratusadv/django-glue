import {createFieldGlue} from "../proxies/fields"

function resolveOwner(root, path) {
    return path.reduce((owner, segment) => {
        if (!Object.prototype.hasOwnProperty.call(owner, segment)) {
            Object.defineProperty(owner, segment, {
                value: {},
                enumerable: false,
                configurable: true,
            })
        }
        return owner[segment]
    }, root)
}

function definePath(root, path, descriptor) {
    const segments = path.split('.')
    const name = segments.pop()
    const owner = resolveOwner(root, segments)
    const existing = Object.getOwnPropertyDescriptor(owner, name)
    if (existing?.configurable === false) return
    Object.defineProperty(owner, name, {
        ...descriptor,
        configurable: true,
    })
}

class GlueAttributeMaterializer {
    constructor() {
        this.pathsByRecord = new WeakMap()
    }

    refresh(record) {
        const proxy = record.proxy
        if (!proxy) return

        const fields = record.staticData.fields || {}
        const childPaths = new Set(Object.keys(record.staticData.children || {}))
        const callablePaths = Object.keys(record.staticData.callables || {})
        const paths = new Set([
            ...Object.keys(fields),
            ...childPaths,
            ...callablePaths,
        ])
        for (const previousPath of this.pathsByRecord.get(record) || []) {
            if (paths.has(previousPath)) continue
            const segments = previousPath.split('.')
            const name = segments.pop()
            let owner = proxy
            for (const segment of segments) owner = owner?.[segment]
            if (owner) delete owner[name]
        }
        this.pathsByRecord.set(record, paths)
        proxy._fields ||= {}

        Object.entries(fields).forEach(([fieldPath, staticData]) => {
            const valuePath = staticData.value_path || fieldPath
            const fieldName = fieldPath.split('.').at(-1)
            const current = proxy._fields[fieldPath]
            const field = createFieldGlue({
                owner: proxy,
                name: fieldName,
                fieldPath,
                stateKey: valuePath,
                metadata: {
                    ...staticData,
                    ...record.getFieldComputed(fieldPath),
                },
                existingField: current,
            })
            proxy._fields[fieldPath] = field

            if (!childPaths.has(fieldPath)) {
                definePath(proxy, fieldPath, {
                    get() {
                        proxy._ensureLoaded?.()
                        return record.getValue(valuePath)
                    },
                    ...(staticData.editable ? {
                        set(value) {
                            field.value = value?.__glue__isFieldProxy ? value.value : value
                        },
                    } : {}),
                    enumerable: true,
                })
            }
        })

        Object.keys(proxy._fields).forEach(path => {
            if (!Object.prototype.hasOwnProperty.call(fields, path)) {
                delete proxy._fields[path]
            }
        })

        callablePaths.forEach(path => {
            if (
                !path.includes('.')
                && !Object.prototype.hasOwnProperty.call(proxy, path)
                && typeof proxy[path] === 'function'
            ) return
            definePath(proxy, path, {
                value: async kwargs => await proxy._callAttribute(path, kwargs || {}),
                enumerable: false,
                writable: false,
            })
        })

        record.setEditablePaths(
            Object.entries(fields)
                .filter(([, descriptor]) => descriptor.editable === true)
                .map(([, descriptor]) => descriptor.value_path),
        )
    }
}

export {definePath}
export default GlueAttributeMaterializer
