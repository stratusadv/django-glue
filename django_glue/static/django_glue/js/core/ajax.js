async function glue_ajax_request(
    unique_name,
    action,
    data = {},
    options = {
        content_type: 'application/json',
        method: 'POST',
    },
) {
    return await glue_fetch(DJANGO_GLUE_AJAX_URL, {
        ...options,
        payload: {
            'unique_name': unique_name,
            'action': action,
            'data': data,
        }
    })
}


function format_get_url(url, payload = {}) {
    let formatted_url = new URL(window.location.origin + url)

    Object.entries(payload).forEach(([key, value]) => {
        formatted_url.searchParams.append(key, value)
    })

    return formatted_url.pathname + formatted_url.search
}


async function glue_fetch(
    url,
    {
        payload = {},
        method = 'POST',
        content_type = 'application/json',
        response_type = 'json',
        header_options = {},
    } = {}
) {
    const csrf_token = glue_get_cookie('csrftoken')

    const headers = {
        ...header_options,
    }

    if (method !== 'GET' && method !== 'HEAD') {
        headers['Content-Type'] = content_type
        headers['X-CSRFToken'] = csrf_token
    }

    const request_options = {
        method,
        headers,
    }

    if (method !== 'GET' && method !== 'HEAD') {
        request_options.body = JSON.stringify(payload)
    } else {
        url = format_get_url(url, payload)
    }

    try {
        const response = await fetch(url, request_options)

        if (!response.ok) {
            const errorBody = await response.text()
            throw new Error(`HTTP error ${response.status}: ${errorBody}`)
        }

        switch (response_type) {
            case 'json':
                return await response.json()
            case 'text':
                return await response.text()
            case 'blob':
                return await response.blob()
            default:
                return response
        }
    } catch (error) {
        console.error('Fetch error:', error)
        throw error
    }
}
