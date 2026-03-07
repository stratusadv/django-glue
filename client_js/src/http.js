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

    try {
        const actionResponse = await fetch(url, options)

        if (!actionResponse.ok) {
            throw Error(`An error occurred when sending a glue http request: ${await actionResponse.text()}`)
        }

        return {
            ok: actionResponse.ok,
            body: await actionResponse.clone().text(),
            httpResponse: actionResponse,
            data: actionResponse.ok ? await actionResponse.json() : null
        }
    } finally {
        clearTimeout(timeoutId);
    }
}

export async function sendJsonPostRequest(url, data, csrfProtected = true){
    return await sendHttpRequest(url, {
        body: JSON.stringify(!!data ? data : {}),
        method: 'POST',
        contentType: 'application/json',
        csrfProtected
    })
}

export async function sendActionRequest({uniqueName, action, payload, contextData}) {
    const url = `${actionUrlPath}/${uniqueName}/${action}/`
    const data = {payload, context_data: contextData}

    return await sendJsonPostRequest(url, data)
}

export async function sendKeepLiveRequest(uniqueNames) {
    return await sendJsonPostRequest(keepLiveUrl, {'unique_names': uniqueNames})
}