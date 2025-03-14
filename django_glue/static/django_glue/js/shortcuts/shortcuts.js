function django_glue_view_render_inner(url, target_element, get_parameters = {}) {
    let view_glue = new ViewGlue(url)
    view_glue.render_inner(target_element, get_parameters)
}


function django_glue_view_render_outer(url, target_element, get_parameters = {}) {
    let view_glue = new ViewGlue(url)
    view_glue.render_outer(target_element, get_parameters)
}


function parse_json_data(json_data) {
    return JSON.parse(json_data)
}
