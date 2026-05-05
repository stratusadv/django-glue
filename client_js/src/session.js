import {sendJsonGetRequest} from "./http";
import {SESSION_DATA_URL} from "./constants";

export async function updateDjangoGlueSessionData() {
    let session_data = await sendJsonGetRequest(`${SESSION_DATA_URL}/`)
    window.django_glue_session_data = session_data

    for (key in window.django_glue_session_data) {
        window.django_glue_keep_live.add_unique_name(key)
    }
}