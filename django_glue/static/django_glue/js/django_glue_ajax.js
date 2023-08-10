async function glue_ajax_request(
    unique_name,
    action,
    data = {},
    content_type = 'application/json',
    method = 'POST',
) {
    const request_options = {
        method: method,
        headers: {
            'Content-Type': content_type,
            'X-CSRFToken': glue_get_cookie('csrftoken'),
        },
        body: JSON.stringify({
            'unique_name': unique_name,
            'action': action,
            'data': data,
        }),
    }

    const response = await fetch(DJANGO_GLUE_AJAX_URL, request_options);
    if (!response.ok) {
        throw new Error(`HTTP error ${response.status}`);
    }

    if(content_type === 'application/json') {
        return response.json();
    }
    else {
        return response;
    }
}
