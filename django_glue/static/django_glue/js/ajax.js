import {csrf_token} from "./csrf.js";
import {add_message} from "./message.js";

function post_ajax(url, data) {
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
            add_message(data['type'], data['message_title'], data['message_body'])
        })
        .catch((error) => {
            console.error('Error:', error)
        });
}

export { post_ajax }