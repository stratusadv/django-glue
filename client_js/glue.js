import './src/proxies';

import GlueClient from './src/client'
import { ViewGlue } from './src/view'

const Glue = new GlueClient()
window.Glue = Glue
window.ViewGlue = ViewGlue
