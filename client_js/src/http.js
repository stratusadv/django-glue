import {actionUrlPath, keepLiveUrl} from "./constants";
import {getConfig} from "./config";

function getHttpCookie(name) {
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

export async function sendHttpRequest(url, requestOptions = {
    body: '',
    method: 'GET',
    contentType: 'application/json',
    csrfProtected: true,
    timeout: null,
}) {
    const timeoutMs = requestOptions.timeout ?? getConfig().requestTimeoutMs;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

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
        options.headers['X-CSRFToken'] = getHttpCookie('csrftoken')
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
    }
    finally {
        clearTimeout(timeoutId);
    }
}

export async function sendJsonPostRequest(url, data, csrfProtected = true){
    return await sendHttpRequest(url, {
        body: JSON.stringify(data ?? {}),
        method: 'POST',
        contentType: 'application/json',
        csrfProtected
    })
}

export async function sendFormPostRequest(url, data, csrfProtected = true){
    return await sendHttpRequest(url, {
        body: data,
        method: 'POST',
        contentType: 'multipart/form-data',
        csrfProtected
    })
}

export async function sendActionRequest({uniqueName, action, payload, contextData}) {
    const url = `${actionUrlPath}/${uniqueName}/${action}/`

    if (payload instanceof FormData){
        payload.append('context_data', JSON.stringify(contextData))
        return await sendFormPostRequest(url, payload)
    }

    return await sendJsonPostRequest(url, {post_data: payload, context_data: contextData})
}

export async function sendKeepLiveRequest(uniqueNames) {
    return await sendJsonPostRequest(keepLiveUrl, {'unique_names': uniqueNames})
}