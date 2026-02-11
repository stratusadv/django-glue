import {actionUrl} from "./constants";

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
}) {
    const options = {
        method: requestOptions.method,
        headers: {
            'Content-Type': requestOptions.contentType,
        }
    }

    if (options.method === 'POST') {
        options.body = requestOptions.body
    }

    if (requestOptions.csrfProtected) {
        options.headers['X-CSRFToken'] = getHttpCookie('csrftoken')
    }

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
}

export async function sendJsonPostRequest(url, data, csrfProtected = true){
    return await sendHttpRequest(url, {
        body: JSON.stringify(!!data ? data : {}),
        method: 'POST',
        contentType: 'application/json',
        csrfProtected
    })
}

export async function sendActionRequest(payload = {}) {
    return await sendJsonPostRequest(actionUrl, payload)
}
