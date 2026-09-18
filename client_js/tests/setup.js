import {GlobalRegistrator} from '@happy-dom/global-registrator'

GlobalRegistrator.register()

// Glue's client requires Alpine.js. Import it only once happy-dom is
// registered, because Alpine reads `document` and `window` when it loads.
const {default: Alpine} = await import('alpinejs')
await import('../src/alpine')
globalThis.Alpine = Alpine
Alpine.start()

global.fetch = async () => new Response(JSON.stringify({
    result: {},
    state: {},
    policy: {},
    metadata: {},
    messages: [],
}), {status: 200, headers: {'Content-Type': 'application/json'}})
