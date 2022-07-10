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

function get_attribute_string(attribute) {
    return DJANGO_GLUE_ATTRIBUTE_PREFIX + '-' + attribute
}

function live_value_update(unique_name, method, field_name, value) {
    return debounce(function () {
        post_ajax(
            {
                'unique_name': unique_name,
                'method': method,
                'field_name': field_name,
                'value': value,
            },
        )
    })
}

function process_glue_connection(el) {
    let update = el.getAttribute(get_attribute_string('update'))
    let type = el.getAttribute('type')
    let field_name = el.getAttribute(get_attribute_string('field-name'))
    let field_value = el.getAttribute(get_attribute_string('field-value'))
    let unique_name = el.getAttribute(get_attribute_string('unique-name'))

    if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
        el.value = field_value
        if (update === 'live') {
            el.addEventListener('keyup', function () {
                live_value_update(unique_name, 'update', field_name, el.value)
            })
        }
    }

    // if (input_method === 'live') {
    //     el.value = input_value
    //     el.addEventListener('keyup', function () {
    //         debounce(function () {
    //             post_ajax(
    //                 {
    //                     'type': type,
    //                     'method': 'update',
    //                     'unique_name': unique_name,
    //                     'field_name': el.getAttribute('glue-field-name'),
    //                     'value': el.value,
    //                 },
    //             )
    //         })
    //     })
    // } else if (input_method === 'form') {
    //     el.value = input_value
    // }
    //
    // if (input_type === 'submit') {
    //     el.addEventListener('click', function () {
    //         if (input_method === 'update') {
    //             post_ajax(
    //                 {
    //                     'type': type,
    //                     'method': 'update',
    //                     'unique_name': unique_name,
    //                     'form_values': get_form_values(unique_name),
    //                 },
    //             )
    //         } else if (input_method === 'create') {
    //             post_ajax(
    //                 {
    //                     'type': type,
    //                     'method': 'create',
    //                     'unique_name': unique_name,
    //                     'form_values': get_form_values(unique_name),
    //                 },
    //             )
    //         }
    //     })
    // }
    //
    // if (input_type === 'query_set') {
    //     post_ajax_return(
    //         {
    //             'type': type,
    //             'method': 'view',
    //             'unique_name': unique_name,
    //         },
    //     ).then(response => response.json())
    //         .then(data => {
    //             const template_display = document.querySelector('[glue-component-display="' + unique_name + '"]')
    //             const template = template_display.querySelector('[glue-component]')
    //
    //
    //             for (let id in data['data']) {
    //                 let model_object = data['data'][id]
    //                 let node_display = template.content.cloneNode(true)
    //                 for (let field in model_object) {
    //                     let value = model_object[field]
    //                     let template_value = node_display.querySelector('[glue-component-value="' + unique_name + '.'+field+'"]')
    //                     if(template_value !== null) {
    //                         template_value.innerHTML = value
    //                     }
    //                 }
    //                 // node_display.querySelector('[glue-component-value="' + unique_name + '.char"]').innerHTML = model_object['char']
    //
    //                 el.appendChild(node_display)
    //             }
    //
    //             // el.innerHTML = JSON.stringify(data['data'])
    //             // console.log(data['data'])
    //             add_message(data['type'], data['message_title'], data['message_body'])
    //         })
    // }

}

document.querySelectorAll('[' + get_attribute_string("connection") + ']').forEach(process_glue_connection)

