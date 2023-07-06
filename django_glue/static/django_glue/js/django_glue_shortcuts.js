function glue_view_render_inner(url, target_element) {
    let glue_view = new GlueView(url)
    glue_view.render_inner(target_element)
}

function glue_view_render_outer(url, target_element) {
    let glue_view = new GlueView(url)
    glue_view.render_outer(target_element)
}