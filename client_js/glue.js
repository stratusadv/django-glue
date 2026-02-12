import GlueAdapterManager from './src/manager'
import {ModelGlueAdapter} from './src/adapters/model';

// Glue type classes are added to the window so they are in scope for
// type registration via string literal in GlueManager.#registerGlueTypes()
window.ModelGlueAdapter = ModelGlueAdapter

const Glue = new GlueAdapterManager()
window.Glue = Glue