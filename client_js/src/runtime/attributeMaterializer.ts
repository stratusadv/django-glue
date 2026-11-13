import {createValueAttribute} from "../proxies/attributes"
import type {GlueValueAttribute} from "../proxies/attributes"
import type {GlueValueAttributeRecord} from "../proxies/attributes/base"
import type GlueAddressRecord from "./addressRecord"
import {isPlainObject} from "./state"

// A proxy's value attributes, children and callables are defined on it by path at
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
// errors from the attribute's computed data.
function memberRecord(record: GlueAddressRecord, valuePath: string, fieldPath: string): GlueValueAttributeRecord {
    return {
        getValue: name => (record.getValue(valuePath) as GlueMembers | null | undefined)?.[name],
        setValue: (name, value) => {
            const members = record.getValue(valuePath) as GlueMembers | null | undefined
            if (members) members[name] = value
        },
        getValueComputedData: name => ({
            errors: record.getValueComputedData(fieldPath).field_errors?.[name] || [],
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

        const valueAttributes = record.staticData.value_attributes || {}
        const childPaths = new Set(Object.keys(record.staticData.children || {}))
        const callablePaths = Object.keys(record.staticData.callables || {})
        const paths = new Set([
            ...Object.keys(valueAttributes),
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
        proxy._valueAttributes ||= {}
        // Read back through the proxy, which is reactive: writes to the plain
        // object just assigned would not be tracked.
        const proxyValueAttributes = proxy._valueAttributes
        const attributePaths = new Set(Object.keys(valueAttributes))

        Object.entries(valueAttributes).forEach(([fieldPath, schema]) => {
            const valuePath = schema.value_path || fieldPath
            const fieldName = fieldPath.split('.').at(-1)!
            const current = proxyValueAttributes[fieldPath]
            const field = createValueAttribute({
                owner: proxy,
                name: fieldName,
                fieldPath,
                stateKey: valuePath,
                presentation: {
                    ...schema,
                    ...record.getValueComputedData(fieldPath),
                },
                existingAttribute: current,
            })
            proxyValueAttributes[fieldPath] = field

            // The value's own fields are reached beside it, as
            // `owner.attribute.$fields.<name>`, the way a form's are.
            let memberFields: Record<string, GlueValueAttribute> | null = null
            if (schema.fields) {
                const memberOwner = {_record: memberRecord(record, valuePath, fieldPath)}
                memberFields = {}
                for (const [memberName, memberSchema] of Object.entries(schema.fields)) {
                    const memberPath = `${fieldPath}.${memberName}`
                    attributePaths.add(memberPath)
                    proxyValueAttributes[memberPath] = createValueAttribute({
                        owner: memberOwner,
                        name: memberName,
                        stateKey: memberName,
                        presentation: memberSchema,
                        existingAttribute: proxyValueAttributes[memberPath],
                    })
                    memberFields[memberName] = proxyValueAttributes[memberPath]
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
                    ...(schema.editable ? {
                        set(value: {__glue__isValueAttribute?: boolean, value?: unknown} | null | undefined) {
                            field.value = value?.__glue__isValueAttribute ? value.value : value
                        },
                    } : {}),
                    enumerable: true,
                })
            }
        })

        Object.keys(proxyValueAttributes).forEach(path => {
            if (!attributePaths.has(path)) {
                delete proxyValueAttributes[path]
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
            Object.entries(valueAttributes)
                .filter(([, schema]) => schema.editable === true)
                .map(([, schema]) => schema.value_path),
        )
        record.setWriteOnlyPaths(
            Object.entries(valueAttributes)
                .filter(([, schema]) => schema.write_only === true)
                .map(([, schema]) => schema.value_path),
        )
    }
}

export {definePath}
export default GlueAttributeMaterializer
