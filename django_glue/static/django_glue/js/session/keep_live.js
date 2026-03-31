class DjangoGlueKeepLive {
    constructor(keep_live_interval_milliseconds) {
        window.django_glue_keep_live_unique_names = []
        window.django_glue_session_data = {}
        this.last_updated_datetime_milliseconds = 0
        this.keep_live_interval_milliseconds = keep_live_interval_milliseconds
    }

    set_last_updated_date_time() {
        this.last_updated_datetime_milliseconds = Date.now()
    }

    check_expired() {
        let is_expired = (Date.now() - this.last_updated_datetime_milliseconds) > (this.keep_live_interval_milliseconds + 5000)

        if (is_expired) {
            this.confirm_reload()
        } else {
            setTimeout(() => {
                this.check_expired()
            }, 3000)
        }
    }

    confirm_reload() {
        let confirmation = confirm('Session expired. Do you want to reload the page?')

        if (confirmation) {
            window.location.reload()
        }
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
            this.confirm_reload()
        } else {
            this.set_last_updated_date_time()
        }
    }
}
