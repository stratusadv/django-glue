class GlueKeepLive {
    constructor() {
        window.glue_keep_live_unique_names = []
        window.glue_session_data = {}
    }

    add_unique_name(unique_name) {
        if (!window.glue_keep_live_unique_names.includes(unique_name)) {
            window.glue_keep_live_unique_names.push(unique_name)
        }
    }

    async update(keep_live_url) {
        const request_options = {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': glue_get_cookie('csrftoken'),
            },
            body: JSON.stringify({
                'unique_names': window.glue_keep_live_unique_names,
            }),
        }
        await fetch(keep_live_url, request_options)
    }
}

