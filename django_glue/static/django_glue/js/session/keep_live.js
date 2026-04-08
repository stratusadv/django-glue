class DjangoGlueKeepLive {
    constructor(keep_live_interval_milliseconds) {
        window.django_glue_keep_live_unique_names = []
        window.django_glue_session_data = {}
        this.last_updated_datetime_milliseconds = Date.now()
        this.keep_live_interval_milliseconds = keep_live_interval_milliseconds
        this.keep_live_interval_handle = null
    }

    set_last_updated_date_time() {
        this.last_updated_datetime_milliseconds = Date.now()
    }

    clear_pulse_interval() {
        if (this.keep_live_interval_handle) {
            clearInterval(this.keep_live_interval_handle)
            this.keep_live_interval_handle = null
        }
    }

    check_expired() {
        const now_last_expired_delta = (Date.now() - this.last_updated_datetime_milliseconds)
        let is_expired = now_last_expired_delta > (this.keep_live_interval_milliseconds + 5000)

        if (is_expired) {
            this.clear_pulse_interval()
            this.confirm_reload()
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
        this.check_expired()

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

    init() {
        this.keep_live_interval_handle = setInterval(() => {
            window.django_glue_keep_live.update(DJANGO_GLUE_KEEP_LIVE_URL)
        }, this.keep_live_interval_milliseconds)
    }
}
