import type AlpineType from "alpinejs"
import type GlueClientClass from "./client"
import type {parseJsonScriptById as parseJsonScriptByIdFunction, resolveUrl as resolveUrlFunction} from "./utils"

declare global {
    // The page's client, assigned by the django_glue.html template once it
    // has constructed one.
    var Glue: GlueClientClass | undefined

    // What the bundle exposes for that template and for application code.
    var GlueClient: typeof GlueClientClass
    var parseJsonScriptById: typeof parseJsonScriptByIdFunction
    var resolveUrl: typeof resolveUrlFunction
    var Alpine: typeof AlpineType | undefined
}
