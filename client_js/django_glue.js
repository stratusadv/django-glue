import GlueClient from "./src/client"
import { parseJsonScriptById } from "./src/utils"

globalThis.GlueClient = GlueClient
globalThis.parseJsonScriptById = parseJsonScriptById

export {GlueClient, parseJsonScriptById}
