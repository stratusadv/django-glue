import {post_ajax} from "./ajax.js";
import {debounce} from "./debouce.js";

function get_form_values(unique_name) {
    let form_input_list = document.querySelectorAll('[glue-connect]')
    let form_json = {}

    for(let i = 0; i < form_input_list.length; i++) {
        form_json[form_input_list[i].getAttribute('glue-field-name')] = form_input_list[i].value
    }

    return form_json
}

function process_glue_connect(el) {
    let input_method = el.getAttribute('glue-method')
    let input_type = el.getAttribute('glue-connect')
    let input_value = el.getAttribute('glue-field-value')
    let unique_name = el.getAttribute('glue-unique-name')

    if (input_method === 'live') {
        el.value = input_value
        el.addEventListener('keyup', function () {
            debounce(function () {
                post_ajax(
                    DJANGO_GLUE_AJAX_URL,
                    {
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
                    DJANGO_GLUE_AJAX_URL,
                    {
                        'method': 'update',
                        'unique_name': unique_name,
                        'form_values': get_form_values(unique_name),
                    },
                )
            } else if (input_method === 'create') {
                post_ajax(
                    DJANGO_GLUE_AJAX_URL,
                    {
                        'method': 'create',
                        'unique_name': unique_name,
                        'form_values': get_form_values(unique_name),
                    },
                )
            }
        })
    }

}

document.querySelectorAll('[glue-connect]').forEach(process_glue_connect)

