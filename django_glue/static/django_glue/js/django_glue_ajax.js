async function glue_ajax_request(unique_name, action, data = {}, method='QUERY') {
    const request_options = {
        method: method,
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': glue_get_cookie('csrftoken'),
        },
        body: JSON.stringify({
            'unique_name': unique_name,
            'action': action,
            'data': data,
        }),
    };

    const response = await fetch(DJANGO_GLUE_AJAX_URL, request_options);
    if (!response.ok) {
        throw new Error(`HTTP error ${response.status}`);
    }

    console.log(response)

    return await response.json();
}
