function isPlainObject(value) {
    return Object.prototype.toString.call(value) === '[object Object]'
}

function cloneValue(value) {
    if (value === null || value === undefined) {
        return value
    }

    if (value instanceof Date) {
        return new Date(value)
    }

    if (Array.isArray(value)) {
        return value.map(item => cloneValue(item))
    }

    if (isPlainObject(value)) {
        return Object.fromEntries(
            Object.entries(value).map(([key, item]) => [key, cloneValue(item)])
        )
    }

    return value
}

function parseFieldValue(field, value) {
    if (value === null || value === undefined || value === '' || value instanceof Date) {
        return value
    }

    const type = field?.type
    if (type === 'DateField') {
        return new Date(`${value}T00:00:00`)
    }

    if (['DateTimeField', 'SplitDateTimeField'].includes(type)) {
        return new Date(value)
    }

    return value
}

function serializeValue(value) {
    if (value instanceof Date) {
        return value.toISOString()
    }

    if (Array.isArray(value)) {
        return value.map(item => serializeValue(item))
    }

    if (isPlainObject(value)) {
        return Object.fromEntries(
            Object.entries(value).map(([key, item]) => [key, serializeValue(item)])
        )
    }

    return value
}

function parseJsonScriptById(scriptId) {
    return JSON.parse(document.getElementById(scriptId).textContent)
}

export {cloneValue, isPlainObject, parseFieldValue, serializeValue, parseJsonScriptById}
