let debounce_method = null

function debounce(method, interval = 300) {
    clearTimeout(debounce_method);
    debounce_method = setTimeout(method, interval)
}

export { debounce }