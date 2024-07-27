function glue_view_render_inner(url, target_element, get_parameters = {}) {
    let glue_view = new GlueView(url)
    glue_view.render_inner(target_element, get_parameters)
}


function glue_view_render_outer(url, target_element, get_parameters = {}) {
    let glue_view = new GlueView(url)
    glue_view.render_outer(target_element, get_parameters)
}


function parse_json_data(json_data) {
    return JSON.parse(json_data)
}
