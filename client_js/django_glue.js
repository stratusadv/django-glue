import GlueClient from "./src/client"
import { parseJsonScriptById, resolveUrl } from "./src/utils"

globalThis.GlueClient = GlueClient
globalThis.parseJsonScriptById = parseJsonScriptById
globalThis.resolveUrl = resolveUrl

export {GlueClient, parseJsonScriptById, resolveUrl}
