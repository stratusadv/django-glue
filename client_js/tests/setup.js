import {GlobalRegistrator} from '@happy-dom/global-registrator'

GlobalRegistrator.register()

global.fetch = async () => new Response(JSON.stringify({
    result: {},
    state: {},
    policy: {},
    metadata: {},
    messages: [],
}), {status: 200, headers: {'Content-Type': 'application/json'}})
