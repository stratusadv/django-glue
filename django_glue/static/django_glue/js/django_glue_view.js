async function glue_view_ajax_request(url, method= 'GET', headers = {'Content-Type': 'application/json'}, body = {}) {
    const request_options = {
        method: method,
        headers: {
            ...headers,
            'X-CSRFToken': glue_get_cookie('csrftoken'),
        },
        body: JSON.stringify(body),
    };

    const response = await fetch(url, request_options);
    if (!response.ok) {
        throw new Error(`HTTP error ${response.status}`);
    }

    console.log(response)

    return await response.json();
}

function glue_view_inner(url) {
    alert('GLUE A VIEW!!!')
}