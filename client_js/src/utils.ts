function isPlainObject(value: unknown): value is Record<string, unknown> {
    return Object.prototype.toString.call(value) === '[object Object]'
}

function cloneValue<T>(value: T): T {
    if (value === null || value === undefined) {
        return value
    }

    if (value instanceof Date) {
        return new Date(value) as T
    }

    if (Array.isArray(value)) {
        return value.map(item => cloneValue(item)) as T
    }

    if (isPlainObject(value)) {
        return Object.fromEntries(
            Object.entries(value).map(([key, item]) => [key, cloneValue(item)])
        ) as T
    }

    return value
}

function serializeValue(value: unknown): unknown {
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

function parseJsonScriptById<T = unknown>(scriptId: string): T {
    return JSON.parse(document.getElementById(scriptId)!.textContent!)
}

function resolveUrl(urlPathTemplate: string, kwargs: Record<string, string | number> = {}): string {
    let url = urlPathTemplate
    for (const [key, value] of Object.entries(kwargs)) {
        url = url.replace(`\${${key}}`, String(value))
    }
    return url
}

function shouldJsonSerializePostData(value: unknown): boolean {
    if (typeof value !== 'object' || value === null) {
        return false
    }

    if (value instanceof FormData || value instanceof Blob || value instanceof URLSearchParams) {
        return false
    }

    const tag = Object.prototype.toString.call(value)

    return tag === '[object Object]' || tag === '[object Array]'
}

export {
    cloneValue,
    isPlainObject,
    serializeValue,
    shouldJsonSerializePostData,
    parseJsonScriptById,
    resolveUrl,
}
