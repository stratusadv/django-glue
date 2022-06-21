import {csrf_token} from "./csrf.js";
import {add_message} from "./message.js";

function post_ajax(url, data) {
    let response_data
    fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrf_token,
        },
        body: JSON.stringify(data),
    })
        .then(response => response.json())
        .then(data => {
            console.log('Success:', data)
            response_data = data
            add_message(data['type'], data['message_title'], data['message_body'])

        })
        .catch((error) => {
            console.error('Error:', error)
        });
    return response_data
}

export { post_ajax }