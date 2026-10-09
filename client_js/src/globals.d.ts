import type GlueClient from "./client"

// The page's client, assigned by the django_glue.html template once it has
// constructed one.
declare global {
    var Glue: GlueClient | undefined
}
