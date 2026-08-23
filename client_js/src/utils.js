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
    if (value === null || value === undefined) {
        return value
    }

    if (typeof value === 'function') {
        return undefined
    }

    if (value instanceof Date) {
        return value.toISOString()
    }

    if (Array.isArray(value)) {
        return value.map(item => serializeValue(item))
    }

    if (isPlainObject(value)) {
        return Object.fromEntries(
            Object.entries(value)
                .filter(([key, item]) => typeof item !== 'function' && !key.startsWith('_'))
                .map(([key, item]) => [key, serializeValue(item)])
        )
    }

    return value
}

function parseJsonScriptById(scriptId) {
    return JSON.parse(document.getElementById(scriptId).textContent)
}

function resolveElement(target) {
    return typeof target === 'string' ? document.querySelector(target) : target
}

function htmlToFragment(html) {
    const template = document.createElement('template')
    template.innerHTML = html
    return template.content
}

function resolveUrl(urlPathTemplate, kwargs = {}) {
    let url = urlPathTemplate
    for (const [key, value] of Object.entries(kwargs)) {
        url = url.replace(`\${${key}}`, value)
    }
    return url
}

function shouldJsonSerializePostData(value) {
    if (typeof value !== 'object' || value === null) {
        return false
    }

    if (value instanceof FormData || value instanceof Blob || value instanceof URLSearchParams) {
        return false
    }

    const tag = Object.prototype.toString.call(value)

    return tag === '[object Object]' || tag === '[object Array]'
}

function reactiveSelf(object) {
    return globalThis.Alpine?.reactive?.(object) ?? object
}

export {
    cloneValue,
    isPlainObject,
    parseFieldValue,
    serializeValue,
    shouldJsonSerializePostData,
    parseJsonScriptById,
    reactiveSelf,
    resolveUrl,
    resolveElement,
    htmlToFragment,
}
