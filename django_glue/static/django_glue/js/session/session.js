async function update_session_data() {
    let response = await glue_fetch(DJANGO_SESSION_DATA_URL, {
        method: 'GET',
        response_type: 'json',
    })
    console.log(response)
}