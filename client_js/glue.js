import GlueProxyManager from './src/manager'
import {GlueModelProxy} from './src/proxies/model';

// Glue type classes are added to the window so they are in scope for
// type registration via string literal in GlueManager.#registerGlueTypes()
window.GlueModelProxy = GlueModelProxy

const Glue = new GlueProxyManager()
window.Glue = Glue