import type {GlueComputedData, GlueFieldComputed, GluePolicyPayload} from "../wire"

// An object's values by state path: its signed snapshot overlaid with its
// derived output.
type GlueValues = Record<string, unknown>

function isPlainObject(value: unknown): value is Record<string, unknown> {
    if (value === null || typeof value !== 'object') return false
    const prototype = Object.getPrototypeOf(value)
    return prototype === Object.prototype || prototype === null
}

function cloneValue<T>(value: T): T {
    if (value === null || value === undefined) return value
    if (value instanceof Date) return new Date(value) as T
    if (Array.isArray(value)) return value.map(item => cloneValue(item)) as T
    if (isPlainObject(value)) {
        return Object.fromEntries(
            Object.entries(value).map(([key, item]) => [key, cloneValue(item)])
        ) as T
    }
    return value
}

function valuesEqual(left: unknown, right: unknown): boolean {
    if (Object.is(left, right)) return true
    if (left instanceof Date && right instanceof Date) {
        return left.valueOf() === right.valueOf()
    }
    if (Array.isArray(left) && Array.isArray(right)) {
        return left.length === right.length
            && left.every((item, index) => valuesEqual(item, right[index]))
    }
    if (isPlainObject(left) && isPlainObject(right)) {
        const leftKeys = Object.keys(left)
        const rightKeys = Object.keys(right)
        return leftKeys.length === rightKeys.length
            && leftKeys.every(key => (
                Object.prototype.hasOwnProperty.call(right, key)
                && valuesEqual(left[key], right[key])
            ))
    }
    return false
}

function observeValue<T>(value: T, onMutation: () => void, cache = new WeakMap<object, unknown>()): T {
    if (!Array.isArray(value) && !isPlainObject(value)) return value
    if (cache.has(value)) return cache.get(value) as T

    // An array is observed through its keys too, so it is read as a record.
    const container = value as Record<string | symbol, unknown>
    Object.keys(container).forEach(key => {
        container[key] = observeValue(container[key], onMutation, cache)
    })

    const observed = new Proxy(container, {
        set(target, key, nextValue) {
            const changed = !valuesEqual(target[key], nextValue)
            target[key] = observeValue(nextValue, onMutation, cache)
            if (changed) onMutation()
            return true
        },
        deleteProperty(target, key) {
            if (!Object.prototype.hasOwnProperty.call(target, key)) return true
            delete target[key]
            onMutation()
            return true
        },
    })
    cache.set(value, observed)
    return observed as T
}

function assembleAuthoritative(
    policy: Pick<GluePolicyPayload, 'state_snapshot'> | null | undefined,
    computedData: GlueComputedData | null | undefined,
): GlueValues {
    const values = cloneValue(policy?.state_snapshot || {})
    Object.entries(computedData || {}).forEach(([path, value]) => {
        if (path !== 'fields') values[path] = cloneValue(value)
    })
    return values
}

function deriveUpdates(canonical: GlueValues, reactiveValues: GlueValues, editablePaths: Iterable<string>): GlueValues {
    return Object.fromEntries(
        Array.from(editablePaths)
            .filter(path => !valuesEqual(canonical[path], reactiveValues[path]))
            .map(path => [path, cloneValue(reactiveValues[path])])
    )
}

function applyUpdates(canonical: GlueValues, updates: GlueValues): GlueValues {
    return {
        ...cloneValue(canonical),
        ...cloneValue(updates),
    }
}

function mergeComputedData(
    current: GlueComputedData | null | undefined,
    incoming: GlueComputedData | null | undefined,
): GlueComputedData {
    const merged = cloneValue(current || {})
    Object.entries(incoming || {}).forEach(([path, value]) => {
        if (path !== 'fields') {
            merged[path] = cloneValue(value)
            return
        }
        const fields = merged.fields = merged.fields || {}
        Object.entries((value || {}) as Record<string, GlueFieldComputed>).forEach(([fieldPath, fieldData]) => {
            fields[fieldPath] = cloneValue(fieldData)
        })
    })
    return merged
}

export type {GlueValues}
export {
    applyUpdates,
    assembleAuthoritative,
    cloneValue,
    deriveUpdates,
    isPlainObject,
    mergeComputedData,
    observeValue,
    valuesEqual,
}
