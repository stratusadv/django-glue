async function update_session_data() {
    let session_data = await glue_fetch(DJANGO_SESSION_DATA_URL, {
        method: 'GET',
        response_type: 'json',
    })

    window.glue_session_data = session_data

    for (key in window.glue_session_data) {
        window.glue_keep_live.add_unique_name(key)
    }
}
