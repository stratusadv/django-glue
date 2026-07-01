/**
 * HTTP client for Django Glue. Handles fetch requests, CSRF tokens, timeouts,
 * and serialization for action and keep-alive requests.
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
                throw Error(`An error occurred when sending a glue http request: ${await response.text()}`)
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
     * Send an action request to the Django Glue action endpoint.
     * @param {Object} options - Action request parameters.
     * @param {string} options.uniqueName - The proxy unique name.
     * @param {string} options.action - The action method name.
     * @param {Object|FormData} [options.payload] - The action payload data.
     * @param {Object} options.contextData - The proxy context data for server-side reconstruction.
     * @param {Object} [options.extraData] - Proxy-type-specific runtime data (e.g., instance_id).
     * @returns {Promise<Object>} Response object.
     */
    async sendActionRequest({uniqueName, action, payload, contextData, extraData = null}) {
        const url = `${this._config.actionUrlPath}${uniqueName}/${action}/`

        if (payload instanceof FormData) {
            payload.append('context_data', JSON.stringify(contextData))
            if (extraData) {
                payload.append('extra_data', JSON.stringify(extraData))
            }
            return await this.sendFormPostRequest(url, payload)
        }

        const requestBody = {
            post_data: payload,
            context_data: contextData,
        }
        if (extraData) {
            requestBody.extra_data = extraData
        }

        return await this.sendJsonPostRequest(url, requestBody)
    }

    /**
     * Send a keep-alive request to renew proxy expiration timestamps.
     * @param {string[]} uniqueNames - Array of proxy unique names to renew.
     * @returns {Promise<Object>} Response object.
     */
    async sendKeepLiveRequest(uniqueNames) {
        return await this.sendJsonPostRequest(this._config.keepLiveUrlPath, {'unique_names': uniqueNames})
    }
}

export default GlueHttp
