import './src/proxies';

import GlueClient from './src/client'
import GlueConfig from "./src/config";
import GlueHttp from "./src/http";

const Glue = new GlueClient()

window.Glue = Glue
window.GlueConfig = GlueConfig
window.GlueHttp = GlueHttp
