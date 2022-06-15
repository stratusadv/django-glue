import {post_ajax} from "./ajax.js";
import {debounce} from "./debouce.js";

function process_glue_connect(el) {
    let input_method = el.getAttribute('glue-method')
    let input_type = el.getAttribute('glue-connect')
    let input_value = el.getAttribute('glue-field-value')

    if (input_method === 'live') {
        el.value = input_value
        el.addEventListener('keyup', function () {
            debounce(function () {
                post_ajax(
                    DJANGO_GLUE_AJAX_URL,
                    {
                        'method': 'update',
                        'unique_name': el.getAttribute('glue-unique-name'),
                        'field_name': el.getAttribute('glue-field-name'),
                        'value': el.value,
                    },
                )
            })
        })
    }

    else if(input_method === 'form') {
        el.value = input_value
    }
}

document.querySelectorAll('[glue-connect]').forEach(process_glue_connect)

