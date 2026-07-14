import {GlueHttpError} from "./errors";

/**
 * HTTP client for Django Glue. Handles fetch requests, CSRF tokens, timeouts,
 * and serialization for bound attribute events.
 */
class GlueHttp {
    /**
     * @param {GlueConfig} config - The Glue configuration instance.
     */
    constructor(config) {
        this._config = config
    }

    /**
     * Retrieve a cookie value by name from `document.cookie`.
     * @param {string} name - The cookie name.
     * @returns {string|null} The decoded cookie value, or `null` if not found.
     */
    getCookie(name) {
        if (document?.cookie !== '') {
            const cookies = document.cookie.split(';').map(cookie => cookie.trim())

            for (const cookie of cookies) {
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    return decodeURIComponent(cookie.substring(name.length + 1))
                }
            }
        }

        return null
    }

    /**
     * Send an HTTP request with timeout, CSRF protection, and content-type handling.
     * @param {string} url - The request URL.
     * @param {Object} [requestOptions] - Request configuration.
     * @param {string} [requestOptions.body=''] - Request body.
     * @param {string} [requestOptions.method='GET'] - HTTP method.
     * @param {string} [requestOptions.contentType='application/json'] - Content-Type header.
     * @param {boolean} [requestOptions.csrfProtected=true] - Whether to attach CSRF token.
     * @param {number|null} [requestOptions.timeoutSeconds=null] - Timeout override; falls back to config default.
     * @returns {Promise<Object>} Response object with `{ok, body, httpResponse, data}`.
     */
    async sendRequest(url, requestOptions = {
        body: '',
        method: 'GET',
        contentType: 'application/json',
        csrfProtected: true,
        timeoutSeconds: null,
    }) {
        const timeoutSeconds = requestOptions.timeoutSeconds ?? this._config.requestTimeoutSeconds
        const controller = new AbortController()
        const timeoutId = setTimeout(() => controller.abort(), (timeoutSeconds * 1000))

        const options = {
            method: requestOptions.method,
            headers: {
                'Content-Type': requestOptions.contentType,
            },
            signal: controller.signal,
        }

        if (options.method === 'POST') {
            options.body = requestOptions.body
        }

        if (requestOptions.csrfProtected) {
            options.headers['X-CSRFToken'] = this.getCookie('csrftoken')
        }

        if (requestOptions.contentType === 'multipart/form-data') {
            // Remove this header here because fetch adds it with the proper boundary if it detects FormData in the body.
            // Including this header when sending FormData causes an error in the backend.
            delete options.headers['Content-Type'];
        }

        try {
            const response = await fetch(url, options)

            if (!response.ok) {
                throw await this._buildRequestError(response)
            }

            return {
                ok: response.ok,
                body: await response.clone().text(),
                httpResponse: response,
                data: response.ok ? await response.json() : null
            }
        } catch (e) {
            throw e
        } finally {
            clearTimeout(timeoutId);
        }
    }

    async _buildRequestError(response) {
        const body = await response.text()
        let payload = null

        try {
            payload = JSON.parse(body)
        } catch (_) {
            // Plain text responses are still supported for non-Glue failures.
        }

        const errorData = payload?.error
        const message = errorData?.message || body
        return new GlueHttpError({
            message,
            status: response.status,
            code: errorData?.code,
            payload: errorData || null,
            responseBody: body,
        })
    }

    /**
     * Send a JSON-encoded POST request.
     * @param {string} url - The request URL.
     * @param {Object} data - The payload to stringify and send.
     * @param {boolean} [csrfProtected=true] - Whether to attach CSRF token.
     * @returns {Promise<Object>} Response object.
     */
    async sendJsonPostRequest(url, data, csrfProtected = true) {
        return await this.sendRequest(url, {
            body: JSON.stringify(data ?? {}),
            method: 'POST',
            contentType: 'application/json',
            csrfProtected
        })
    }

    /**
     * Send a `multipart/form-data` POST request.
     * @param {string} url - The request URL.
     * @param {FormData} data - The FormData payload.
     * @param {boolean} [csrfProtected=true] - Whether to attach CSRF token.
     * @returns {Promise<Object>} Response object.
     */
    async sendFormPostRequest(url, data, csrfProtected = true) {
        return await this.sendRequest(url, {
            body: data,
            method: 'POST',
            contentType: 'multipart/form-data',
            csrfProtected
        })
    }

    /**
     * Send a bound attribute event request to the Django Glue endpoint.
     * Always uses FormData to ensure consistent handling of all data types including files.
     *
     * @param {Object} options - Bound attribute event request parameters.
     * @param {string} options.name - The proxy unique name.
     * @param {string} options.attribute - The bound attribute name.
     * @param {Object} [options.eventKwargs] - Event-specific keyword arguments (e.g., step number, filter params).
     * @param {Object} options.policy - The proxy policy for server-side verification and reconstruction.
     * @param {Object} [options.state] - Proxy-intrinsic runtime state (e.g., form_values, instance_pk).
     * @returns {Promise<Object>} Response object.
     */
    async sendAttributeEventRequest({name, attribute, eventKwargs = null, policy, state = null}) {
        const url = `${this._config.attributeEventUrlPath}${name}/${attribute}/`

        const formData = new FormData()
        formData.append('policy', JSON.stringify(policy))

        if (state) {
            // Extract files from state and append them separately
            const {files, data} = this._extractFiles(state)
            formData.append('state', JSON.stringify(data))

            // Append files directly to FormData, stripping 'instance_data.' prefix
            Object.entries(files).forEach(([key, value]) => {
                const fieldKey = key.replace('instance_data.', '', 1);
                if (value instanceof FileList) {
                    Array.from(value).forEach(file => formData.append(fieldKey, file))
                } else if (Array.isArray(value)) {
                    value.forEach(file => formData.append(fieldKey, file))
                } else {
                    formData.append(fieldKey, value)
                }
            })
        }

        if (eventKwargs) {
            formData.append('event_kwargs', JSON.stringify(eventKwargs))
        }

        return await this.sendFormPostRequest(url, formData)
    }

    /**
     * Extract File/Blob/FileList values from an object, returning files separately.
     * @param {Object} obj - The object to extract files from.
     * @returns {{files: Object, data: Object}} Object with files extracted and remaining data.
     * @private
     */
    _extractFiles(obj) {
        const files = {}
        const data = {}

        const extractFromValue = (value, key) => {
            if (value instanceof File || value instanceof Blob) {
                files[key] = value
                return undefined
            } else if (value instanceof FileList) {
                files[key] = value
                return undefined
            } else if (Array.isArray(value)) {
                // Check if array contains files
                const hasFiles = value.some(v => v instanceof File || v instanceof Blob)
                if (hasFiles) {
                    files[key] = value.filter(v => v instanceof File || v instanceof Blob)
                    const nonFiles = value.filter(v => !(v instanceof File || v instanceof Blob))
                    return nonFiles.length > 0 ? nonFiles : undefined
                }
                return value
            } else if (value && typeof value === 'object') {
                // Recursively handle nested objects
                const nested = this._extractFiles(value)
                Object.entries(nested.files).forEach(([k, v]) => {
                    files[`${key}.${k}`] = v
                })
                return Object.keys(nested.data).length > 0 ? nested.data : undefined
            }
            return value
        }

        Object.entries(obj).forEach(([key, value]) => {
            const result = extractFromValue(value, key)
            if (result !== undefined) {
                data[key] = result
            }
        })

        return {files, data}
    }
}

export default GlueHttp
