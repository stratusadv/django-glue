import GlueClient from "./src/client"
import {installAlpine} from "./src/alpine"
import { parseJsonScriptById, resolveUrl } from "./src/utils"

globalThis.GlueClient = GlueClient
globalThis.parseJsonScriptById = parseJsonScriptById
globalThis.resolveUrl = resolveUrl

installAlpine()

export {GlueClient, parseJsonScriptById, resolveUrl}
