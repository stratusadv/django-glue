function isPlainObject(value) {
    if (value === null || typeof value !== 'object') return false
    const prototype = Object.getPrototypeOf(value)
    return prototype === Object.prototype || prototype === null
}

function cloneValue(value) {
    if (value === null || value === undefined) return value
    if (value instanceof Date) return new Date(value)
    if (Array.isArray(value)) return value.map(item => cloneValue(item))
    if (isPlainObject(value)) {
        return Object.fromEntries(
            Object.entries(value).map(([key, item]) => [key, cloneValue(item)])
        )
    }
    return value
}

function valuesEqual(left, right) {
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

function observeValue(value, onMutation, cache = new WeakMap()) {
    if (!Array.isArray(value) && !isPlainObject(value)) return value
    if (cache.has(value)) return cache.get(value)

    Object.keys(value).forEach(key => {
        value[key] = observeValue(value[key], onMutation, cache)
    })

    const observed = new Proxy(value, {
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
    return observed
}

function assembleAuthoritative(policy, computedData) {
    const values = cloneValue(policy?.state_snapshot || {})
    Object.entries(computedData || {}).forEach(([path, value]) => {
        if (path !== 'fields') values[path] = cloneValue(value)
    })
    return values
}

function deriveUpdates(canonical, reactiveValues, editablePaths) {
    return Object.fromEntries(
        Array.from(editablePaths)
            .filter(path => !valuesEqual(canonical[path], reactiveValues[path]))
            .map(path => [path, cloneValue(reactiveValues[path])])
    )
}

function applyUpdates(canonical, updates) {
    return {
        ...cloneValue(canonical),
        ...cloneValue(updates),
    }
}

function mergeComputedData(current, incoming) {
    const merged = cloneValue(current || {})
    Object.entries(incoming || {}).forEach(([path, value]) => {
        if (path !== 'fields') {
            merged[path] = cloneValue(value)
            return
        }
        merged.fields = merged.fields || {}
        Object.entries(value || {}).forEach(([fieldPath, fieldData]) => {
            merged.fields[fieldPath] = cloneValue(fieldData)
        })
    })
    return merged
}

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
