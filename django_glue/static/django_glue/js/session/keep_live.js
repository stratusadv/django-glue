class DjangoGlueKeepLive {
    constructor() {
        window.django_glue_keep_live_unique_names = []
        window.django_glue_session_data = {}
    }

    add_unique_name(unique_name) {
        if (!window.django_glue_keep_live_unique_names.includes(unique_name)) {
            window.django_glue_keep_live_unique_names.push(unique_name)
        }
    }

    async update(keep_live_url) {
        const request_options = {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': django_glue_get_cookie('csrftoken'),
            },
            body: JSON.stringify({
                'unique_names': window.django_glue_keep_live_unique_names,
            }),
        }

        const response = await fetch(keep_live_url, request_options)

        if (!response.ok) {
            let confirmation = confirm('Session expired. Do you want to reload the page?')

            if (confirmation) {
                window.location.reload()
            }
        }
    }
}
