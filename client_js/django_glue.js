/**
 * Django Glue JavaScript client entry point.
 *
 * Imports proxy classes (registering them on `window`), creates a singleton
 * {@link GlueClient} instance, and exposes it as `window.Glue`.
 */
import './src/proxies';

import GlueClient from './src/client'
import GlueConfig from "./src/config";
import GlueHttp from "./src/http";

/**
 * The singleton Glue client instance. Access as `window.Glue`.
 * @type {GlueClient}
 */
const Glue = new GlueClient()

/** @type {GlueClient} */
window.Glue = Glue

/** @type {Function} */
window.GlueConfig = GlueConfig

/** @type {Function} */
window.GlueHttp = GlueHttp
