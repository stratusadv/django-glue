import {post_ajax, post_ajax_return} from "./ajax.js";
import {debounce} from "./debouce.js";
import {add_message} from "./message.js";

function get_form_values(unique_name) {
    let form_input_list = document.querySelectorAll('[glue-connection]')
    let form_json = {}

    for (let i = 0; i < form_input_list.length; i++) {
        form_json[form_input_list[i].getAttribute('glue-field-name')] = form_input_list[i].value
    }

    console.log(form_json)

    return form_json
}

function get_attribute_string(attribute) {
    return DJANGO_GLUE_ATTRIBUTE_PREFIX + '-' + attribute
}

function live_value_update(unique_name, action, field_name, value) {
    return debounce(function () {
        post_ajax(
            {
                'unique_name': unique_name,
                'action': action,
                'field_name': field_name,
                'value': value,
            },
        )
    })
}

function process_glue_connection(el) {
    let update = el.getAttribute(get_attribute_string('update'))
    let action = el.getAttribute(get_attribute_string('action'))
    let connection = el.getAttribute(get_attribute_string('connection'))
    let field_name = el.getAttribute(get_attribute_string('field-name'))
    let field_value = el.getAttribute(get_attribute_string('field-value'))
    let unique_name = el.getAttribute(get_attribute_string('unique-name'))

    if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
        if (el.type === 'submit') {
            el.addEventListener('click', function () {
                if (action === 'submit_update') {
                    post_ajax(
                        {
                            'connection': connection,
                            'action': 'update',
                            'unique_name': unique_name,
                            'form_values': get_form_values(unique_name),
                        },
                    )
                } else if (action === 'submit_create') {
                    post_ajax(
                        {
                            'connection': connection,
                            'action': 'create',
                            'unique_name': unique_name,
                            'form_values': get_form_values(unique_name),
                        },
                    )
                }
            })
        } else if (connection === 'model_object') {
            el.value = field_value
            if (update === 'live') {
                el.addEventListener('keyup', function () {
                    live_value_update(unique_name, 'update', field_name, el.value)
                })
            }
        }
    }

    if (action === 'list_display') {
        post_ajax_return(
            {
                'connection': connection,
                'action': 'view',
                'unique_name': unique_name,
            },
        ).then(response => response.json())
            .then(data => {
                const template = el.querySelector('[' + get_attribute_string('component') + ']')

                for (let id in data['data']) {
                    let node_display = template.content.cloneNode(true)
                    const event_list = node_display.querySelectorAll('[' + get_attribute_string('event') + ']')
                    for (let i = 0; i < event_list.length; i++) {
                        event_list[i].addEventListener('click', function () {
                            alert('DELETE')
                        })
                    }

                    let model_object = data['data'][id]

                    for (let field in model_object) {
                        let value = model_object[field]
                        let template_value = node_display.querySelector('[glue-component-field="' + field + '"]')
                        if (template_value !== null) {
                            template_value.innerHTML = value
                        }
                    }
                    el.appendChild(node_display)
                }

                add_message(data['type'], data['message_title'], data['message_body'])
            })
    }

}

document.querySelectorAll('[' + get_attribute_string("connection") + ']').forEach(process_glue_connection)

