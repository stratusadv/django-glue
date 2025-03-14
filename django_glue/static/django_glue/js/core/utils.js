function choice_verbose(choice, choices) {
    const choices_object = Object.fromEntries(choices)
    console.log(choices_object)
    return choices_object[choice]
}


function django_glue_debounce(func, wait) {
    let timeout

    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout)
            func(...args)
        }

        clearTimeout(timeout)
        timeout = setTimeout(later, wait)
    }
}


function encodeUniqueName(unique_name) {
    // This formatting must match the formatting in the Django Glue utils.py file
    // Format the unique name to match the formatting in the Django Glue utils.py file
    return encodeURIComponent(unique_name + '|' + window.location.pathname)
}


function is_touch_device() {
    return window.matchMedia('(pointer: coarse)').matches || 'ontouchstart' in window;
}


function simplify_model_fields(field_data) {
    let simplified_data = {}

    for (let key in field_data) {
        simplified_data[key] = field_data[key].value
    }

    return simplified_data
}


function title_string(string) {
    let words = string.split('_')

    let titledWords = words.map(word =>
        word.charAt(0).toUpperCase() + word.slice(1).toLowerCase()
    )

    return titledWords.join(' ')
}
