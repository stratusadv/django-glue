import {csrf_token} from "./csrf.js";

async function ajax_request(method, unique_name, data) {
    const requestOptions = {
        method: method,
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrf_token,
        },
        body: JSON.stringify({
            'unique_name': unique_name,
            'data': data,
        }),
    };

    const response = await fetch(DJANGO_GLUE_AJAX_URL, requestOptions);
    if (!response.ok) {
        throw new Error(`HTTP error ${response.status}`);
    }

    return await response.json();
}

export {ajax_request,}