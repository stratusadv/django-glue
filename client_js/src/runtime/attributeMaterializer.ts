import {createFieldGlue} from "../proxies/fields"
import type {FieldGlue} from "../proxies/fields"
import type {GlueFieldRecord} from "../proxies/fields/base"
import type GlueAddressRecord from "./addressRecord"
import {isPlainObject} from "./state"

// A proxy's fields, children and callables are defined on it by path at
// runtime, so the materializer reads and writes it as a bag of members.
type GlueMembers = Record<string, unknown>

function resolveOwner(root: object, path: string[]): GlueMembers {
    return path.reduce((owner: GlueMembers, segment) => {
        if (!Object.prototype.hasOwnProperty.call(owner, segment)) {
            Object.defineProperty(owner, segment, {
                value: {},
                enumerable: false,
                configurable: true,
            })
        }
        return owner[segment] as GlueMembers
    }, root as GlueMembers)
}

function definePath(root: object, path: string, descriptor: PropertyDescriptor): void {
    const segments = path.split('.')
    const name = segments.pop()!
    const owner = resolveOwner(root, segments)
    const existing = Object.getOwnPropertyDescriptor(owner, name)
    if (existing?.configurable === false) return
    Object.defineProperty(owner, name, {
        ...descriptor,
        configurable: true,
    })
}

// The record of the fields inside one object-valued attribute (a form held as
// state): each reads and writes its own key of that value, and reads its
// errors from the attribute's computed output.
function memberRecord(record: GlueAddressRecord, valuePath: string, fieldPath: string): GlueFieldRecord {
    return {
        getValue: name => (record.getValue(valuePath) as GlueMembers | null | undefined)?.[name],
        setValue: (name, value) => {
            const members = record.getValue(valuePath) as GlueMembers | null | undefined
            if (members) members[name] = value
        },
        getFieldComputed: name => ({
            errors: record.getFieldComputed(fieldPath).field_errors?.[name] || [],
        }),
    }
}

class GlueAttributeMaterializer {
    pathsByRecord: WeakMap<GlueAddressRecord, Set<string>>

    constructor() {
        this.pathsByRecord = new WeakMap()
    }

    refresh(record: GlueAddressRecord): void {
        const proxy = record.proxy
        if (!proxy) return
        const members = proxy as unknown as GlueMembers

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
            const name = segments.pop()!
            let owner: GlueMembers | undefined = members
            for (const segment of segments) owner = owner?.[segment] as GlueMembers | undefined
            if (owner) delete owner[name]
        }
        this.pathsByRecord.set(record, paths)
        proxy._fields ||= {}
        // Read back through the proxy, which is reactive: writes to the plain
        // object just assigned would not be tracked.
        const proxyFields = proxy._fields
        const fieldPaths = new Set(Object.keys(fields))

        Object.entries(fields).forEach(([fieldPath, staticData]) => {
            const valuePath = staticData.value_path || fieldPath
            const fieldName = fieldPath.split('.').at(-1)!
            const current = proxyFields[fieldPath]
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
            proxyFields[fieldPath] = field

            // The value's own fields are reached beside it, as
            // `owner.attribute.$fields.<name>`, the way a form's are.
            let memberFields: Record<string, FieldGlue> | null = null
            if (staticData.fields) {
                const memberOwner = {_record: memberRecord(record, valuePath, fieldPath)}
                memberFields = {}
                for (const [memberName, memberStaticData] of Object.entries(staticData.fields)) {
                    const memberPath = `${fieldPath}.${memberName}`
                    fieldPaths.add(memberPath)
                    proxyFields[memberPath] = createFieldGlue({
                        owner: memberOwner,
                        name: memberName,
                        stateKey: memberName,
                        metadata: memberStaticData,
                        existingField: proxyFields[memberPath],
                    })
                    memberFields[memberName] = proxyFields[memberPath]
                }
            }

            if (!childPaths.has(fieldPath)) {
                definePath(proxy, fieldPath, {
                    get() {
                        const value = record.getValue(valuePath)
                        if (memberFields && isPlainObject(value)) {
                            Object.defineProperty(value, '$fields', {
                                value: memberFields,
                                enumerable: false,
                                configurable: true,
                            })
                        }
                        return value
                    },
                    ...(staticData.editable ? {
                        set(value: {__glue__isFieldProxy?: boolean, value?: unknown} | null | undefined) {
                            field.value = value?.__glue__isFieldProxy ? value.value : value
                        },
                    } : {}),
                    enumerable: true,
                })
            }
        })

        Object.keys(proxyFields).forEach(path => {
            if (!fieldPaths.has(path)) {
                delete proxyFields[path]
            }
        })

        callablePaths.forEach(path => {
            if (
                !path.includes('.')
                && !Object.prototype.hasOwnProperty.call(proxy, path)
                && typeof members[path] === 'function'
            ) return
            definePath(proxy, path, {
                value: async (kwargs?: Record<string, unknown>) => await proxy._callAttribute(path, kwargs || {}),
                enumerable: false,
                writable: false,
            })
        })

        record.setEditablePaths(
            Object.entries(fields)
                .filter(([, descriptor]) => descriptor.editable === true)
                .map(([, descriptor]) => descriptor.value_path),
        )
        record.setWriteOnlyPaths(
            Object.entries(fields)
                .filter(([, descriptor]) => descriptor.write_only === true)
                .map(([, descriptor]) => descriptor.value_path),
        )
    }
}

export {definePath}
export default GlueAttributeMaterializer
