import {csrf_token} from "./csrf.js";

function post_ajax(unique_name, action, data) {
    return axios({
        method: 'post',
        url: DJANGO_GLUE_AJAX_URL,
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrf_token,
        },
        data: {
            'connection': 'model_object',
            'action': action,
            'unique_name': unique_name,
            'form_values': {},
            'data': data,
        }
    })
}

export {post_ajax,}