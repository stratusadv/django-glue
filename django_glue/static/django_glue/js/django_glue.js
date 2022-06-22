import {post_ajax, post_ajax_return} from "./ajax.js";
import {debounce} from "./debouce.js";
import {add_message} from "./message.js";

function get_form_values(unique_name) {
    let form_input_list = document.querySelectorAll('[glue-connect]')
    let form_json = {}

    for (let i = 0; i < form_input_list.length; i++) {
        form_json[form_input_list[i].getAttribute('glue-field-name')] = form_input_list[i].value
    }

    return form_json
}

function process_glue_connect(el) {
    let type = el.getAttribute('glue-type')
    let input_method = el.getAttribute('glue-method')
    let input_type = el.getAttribute('glue-connect')
    let input_value = el.getAttribute('glue-field-value')
    let unique_name = el.getAttribute('glue-unique-name')

    if (input_method === 'live') {
        el.value = input_value
        el.addEventListener('keyup', function () {
            debounce(function () {
                post_ajax(
                    {
                        'type': type,
                        'method': 'update',
                        'unique_name': unique_name,
                        'field_name': el.getAttribute('glue-field-name'),
                        'value': el.value,
                    },
                )
            })
        })
    } else if (input_method === 'form') {
        el.value = input_value
    }

    if (input_type === 'submit') {
        el.addEventListener('click', function () {
            if (input_method === 'update') {
                post_ajax(
                    {
                        'type': type,
                        'method': 'update',
                        'unique_name': unique_name,
                        'form_values': get_form_values(unique_name),
                    },
                )
            } else if (input_method === 'create') {
                post_ajax(
                    {
                        'type': type,
                        'method': 'create',
                        'unique_name': unique_name,
                        'form_values': get_form_values(unique_name),
                    },
                )
            }
        })
    }

    if (input_type === 'query_set') {
        post_ajax_return(
            {
                'type': type,
                'method': 'view',
                'unique_name': unique_name,
            },
        ).then(response => response.json())
            .then(data => {
                const template_display = document.querySelector('[glue-template-display="' + unique_name + '"]')
                const template = template_display.querySelector('[glue-template]')


                for (let id in data['data']) {
                    let model_object = data['data'][id]
                    let node_display = template.content.cloneNode(true)
                    for (let field in model_object) {
                        let value = model_object[field]
                        let template_value = node_display.querySelector('[glue-template-value="' + unique_name + '.'+field+'"]')
                        if(template_value !== null) {
                            template_value.innerHTML = value
                        }
                    }
                    // node_display.querySelector('[glue-template-value="' + unique_name + '.char"]').innerHTML = model_object['char']

                    el.appendChild(node_display)
                }

                // el.innerHTML = JSON.stringify(data['data'])
                // console.log(data['data'])
                add_message(data['type'], data['message_title'], data['message_body'])
            })
    }

}

document.querySelectorAll('[glue-connect]').forEach(process_glue_connect)

