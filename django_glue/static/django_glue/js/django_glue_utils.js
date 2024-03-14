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
    return encodeURIComponent(unique_name + '|' + window.location.pathname)
}