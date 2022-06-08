import {post_ajax} from "./ajax.js";
import {debounce} from "./debouce.js";

function process_glue_connection(el) {
    el.value = el.getAttribute('glue-field-value')
    el.addEventListener('keyup', function () {
        debounce(function () {
            post_ajax(
                DJANGO_GLUE_AJAX_URL,
                {
                    'unique_name': el.getAttribute('glue-unique-name'),
                    'field_name': el.getAttribute('glue-field-name'),
                    'value': el.value,
                },
            )
        })
    })
}

document.querySelectorAll('[glue-connect]').forEach(process_glue_connection)

