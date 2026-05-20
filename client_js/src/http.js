class GlueHttp {
    constructor(config) {
        this._config = config
    }
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

    async sendJsonPostRequest(url, data, csrfProtected = true) {
        return await this.sendRequest(url, {
            body: JSON.stringify(data ?? {}),
            method: 'POST',
            contentType: 'application/json',
            csrfProtected
        })
    }

    async sendFormPostRequest(url, data, csrfProtected = true) {
        return await this.sendRequest(url, {
            body: data,
            method: 'POST',
            contentType: 'multipart/form-data',
            csrfProtected
        })
    }

    async sendActionRequest({uniqueName, action, payload, contextData}) {
        const url = `${this._config.actionUrlPath}${uniqueName}/${action}/`

        if (payload instanceof FormData) {
            payload.append('context_data', JSON.stringify(contextData))
            return await this.sendFormPostRequest(url, payload)
        }

        return await this.sendJsonPostRequest(url, {post_data: payload, context_data: contextData})
    }

    async sendKeepLiveRequest(uniqueNames) {
        return await this.sendJsonPostRequest(this._config.keepLiveUrlPath, {'unique_names': uniqueNames})
    }
}

export default GlueHttp