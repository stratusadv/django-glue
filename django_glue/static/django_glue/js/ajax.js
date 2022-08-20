import {csrf_token} from "./csrf.js";

async function ajax_request(method, unique_name, data) {
    return axios({
        method: method,
        url: DJANGO_GLUE_AJAX_URL,
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrf_token,
        },
        data: {
            'unique_name': unique_name,
            'data': data,
        }
    })
}

export {ajax_request,}