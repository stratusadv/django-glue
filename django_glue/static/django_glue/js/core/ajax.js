async function glue_ajax_request(
    unique_name,
    action,
    data = {},
    content_type = 'application/json',
    method = 'POST',
) {
    return await glue_fetch(DJANGO_GLUE_AJAX_URL, {
        'unique_name': unique_name,
        'action': action,
        'data': data,
    })
}


async function glue_fetch(
    url,
    body = {},
    content_type = 'application/json',
    method = 'POST',
) {
    const request_options = {
        method: method,
        headers: {
            'Content-Type': content_type,
            'X-CSRFToken': glue_get_cookie('csrftoken'),
        },
        body: JSON.stringify(body),
    }

    const response = await fetch(url, request_options)

    if (!response.ok) {
        throw new Error(`HTTP error ${response.status}`)
    }

    if (content_type === 'application/json') {
        return response.json()
    }
    else {
        return response
    }
}
