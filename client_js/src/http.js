import {GlueHttpError} from "./errors"
import {serializeValue} from "./utils"

class GlueHttp {
    constructor(config) {
        this._config = config
    }

    getCookie(name) {
        if (document?.cookie !== '') {
            const cookies = document.cookie.split(';').map(cookie => cookie.trim())
            for (const cookie of cookies) {
                if (cookie.substring(0, name.length + 1) === `${name}=`) {
                    return decodeURIComponent(cookie.substring(name.length + 1))
                }
            }
        }
        return null
    }

    async sendRequest(url, requestOptions = {}) {
        const timeoutSeconds = requestOptions.timeoutSeconds ?? this._config.requestTimeoutSeconds
        const controller = new AbortController()
        const timeoutId = setTimeout(() => controller.abort(), timeoutSeconds * 1000)
        const headers = {}

        if (requestOptions.contentType && requestOptions.contentType !== 'multipart/form-data') {
            headers['Content-Type'] = requestOptions.contentType
        }

        if (requestOptions.csrfProtected !== false) {
            headers['X-CSRFToken'] = this.getCookie('csrftoken')
        }

        try {
            const response = await fetch(url, {
                method: requestOptions.method || 'GET',
                body: requestOptions.body,
                headers,
                signal: controller.signal,
            })

            if (!response.ok) {
                throw await this._buildRequestError(response)
            }

            return {
                ok: response.ok,
                body: await response.clone().text(),
                httpResponse: response,
                data: await response.json(),
            }
        } finally {
            clearTimeout(timeoutId)
        }
    }

    async sendFormPostRequest(url, data, csrfProtected = true) {
        return await this.sendRequest(url, {
            body: data,
            method: 'POST',
            contentType: 'multipart/form-data',
            csrfProtected,
        })
    }

    async sendAttributeRequest({name, policy, state = null, attribute, kwargs = {}}) {
        const formData = new FormData()
        const {files, data} = this._extractFiles(serializeValue(state || {}))

        formData.append('policy', JSON.stringify(policy))
        formData.append('state', JSON.stringify(data))
        formData.append('attribute', attribute)
        formData.append('kwargs', JSON.stringify(kwargs))

        Object.entries(files).forEach(([key, value]) => {
            if (value instanceof FileList) {
                Array.from(value).forEach(file => formData.append(key, file))
            } else if (Array.isArray(value)) {
                value.forEach(file => formData.append(key, file))
            } else {
                formData.append(key, value)
            }
        })

        return await this.sendFormPostRequest(`${this._config.attributeUrlPath}${name}/${attribute}/`, formData)
    }

    _extractFiles(obj) {
        const files = {}
        const data = {}

        const extractFromValue = (value, key) => {
            if (value instanceof File || value instanceof Blob || value instanceof FileList) {
                files[key] = value
                return undefined
            }

            if (Array.isArray(value)) {
                const hasFiles = value.some(item => item instanceof File || item instanceof Blob)
                if (!hasFiles) {
                    return value
                }
                files[key] = value.filter(item => item instanceof File || item instanceof Blob)
                const nonFiles = value.filter(item => !(item instanceof File || item instanceof Blob))
                return nonFiles.length > 0 ? nonFiles : undefined
            }

            if (value && typeof value === 'object') {
                const nested = this._extractFiles(value)
                Object.entries(nested.files).forEach(([nestedKey, fileValue]) => {
                    files[`${key}.${nestedKey}`] = fileValue
                })
                return Object.keys(nested.data).length > 0 ? nested.data : undefined
            }

            return value
        }

        Object.entries(obj || {}).forEach(([key, value]) => {
            const extracted = extractFromValue(value, key)
            if (extracted !== undefined) {
                data[key] = extracted
            }
        })

        return {files, data}
    }

    async _buildRequestError(response) {
        const body = await response.text()
        let payload = null

        try {
            payload = JSON.parse(body)
        } catch (_) {
            // Non-Glue failures may still be plain text.
        }

        const errorData = payload?.error
        return new GlueHttpError({
            message: errorData?.message || body,
            status: response.status,
            code: errorData?.code,
            payload: errorData || null,
            responseBody: body,
        })
    }
}

export default GlueHttp
