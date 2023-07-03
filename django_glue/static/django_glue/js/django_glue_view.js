//Todo: Convert into a class object to stay consistent

async function _glue_view_ajax_request(url, method = 'GET', headers = {}, body = {}) {
    const request_options = {
        method: method,
        headers: {
            ...headers,
            'X-CSRFToken': glue_get_cookie('csrftoken'),
        },
        // body: JSON.stringify(body),
    };

    const response = await fetch(url, request_options);

    if (!response.ok) {
        throw new Error(`HTTP error ${response.status}`);
    }

    return response;

}

function glue_load_view_inner(target_element, url) {
    _glue_view_ajax_request(url).then((response) => {
        return response.text()
    }).then((html) => {
        target_element.innerHTML = html
    })
}

function glue_load_view_outer(target_element, url) {
    _glue_view_ajax_request(url).then((response) => {
        return response.text()
    }).then((html) => {
        target_element.outerHTML = html
    })
}