class GlueKeepLive {
    constructor() {
        window.glue_keep_live_unique_names = []
    }

    add_unique_name(unique_name) {
        if (!window.glue_keep_live_unique_names.includes(unique_name)) {
            window.glue_keep_live_unique_names.push(unique_name)
        }
    }

    update(keep_live_url) {
        const request_options = {
            method: 'QUERY',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': glue_get_cookie('csrftoken'),
            },
            body: JSON.stringify({
                'unique_names': window.glue_keep_live_unique_names,
            }),
        }
        const response = fetch(keep_live_url, request_options)
    }

}

