function glue_debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    }
}

function encodeUniqueName(unique_name) {
    // This formatting must match the formatting in the Django Glue utils.py file
    // Format the unique name to match the formatting in the Django Glue utils.py file
    return encodeURIComponent(unique_name + '|' + window.location.pathname)
}


function simplify_model_fields(field_data) {
    let simplified_data = {}

    for (let key in field_data) {
        simplified_data[key] = field_data[key].value
    }
    return simplified_data
}
