async function update_django_glue_session_data() {
    let session_data = await django_glue_fetch(DJANGO_SESSION_DATA_URL, {
        method: 'GET',
        response_type: 'json',
    })

    window.django_glue_session_data = session_data

    for (key in window.django_glue_session_data) {
        window.django_glue_keep_live.add_unique_name(key)
    }
}
