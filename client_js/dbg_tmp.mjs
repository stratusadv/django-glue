import {GlobalRegistrator} from '@happy-dom/global-registrator'
GlobalRegistrator.register()
const {default: Alpine} = await import('alpinejs')
await import('./src/alpine')
globalThis.Alpine = Alpine
Alpine.start()

import GlueClient from './src/client.js'
import {createEntry, createPolicyToken} from './tests/testUtils.js'

const formPolicy = {
    name: 'entry_form', namespace: 'form', address: 'form#test',
    attributes: ['validate'], state_snapshot: {name: 'Ada'},
    identity: {target_pk: null},
}
const ownerPolicy = {
    name: 'dashboard', namespace: 'template', address: 'dashboard#test',
    attributes: ['save'], children: {entry_form: 'form#test'}, state_snapshot: {},
}
const client = new GlueClient({objects: [
    createEntry({
        policy: ownerPolicy,
        staticData: {
            children: {entry_form: {kind: 'form', nullable: false}},
            callables: {save: {allowed_arguments: []}},
        },
    }),
    createEntry({
        policy: formPolicy,
        staticData: {callables: {validate: {allowed_arguments: []}}},
    }),
]})
globalThis.Glue = client
const dashboard = client.template.dashboard
const form = dashboard.entry_form
const originalToken = form._record.policyToken
const repairToken = createPolicyToken(formPolicy)
console.log('parent:', form._record.parent)
console.log('owner record exists:', !!client._registry.getProxy('dashboard#test'))
let step = 0
client.http.sendAttributeRequest = async (params) => {
    step++
    console.log(`call ${step}:`, JSON.stringify({address: params.address, attribute: params.attribute, reintroduce: params.reintroduce, token: params.policyToken === originalToken ? 'ORIGINAL' : (params.policyToken === repairToken ? 'REPAIR' : 'OTHER')}))
    if (params.attribute === 'validate') {
        if (params.policyToken === originalToken) {
            return {data: {objects: [{address: 'form#test', error: {code: 'policy_expired', message: 'policy expired'}}]}}
        }
        return {data: {objects: [{address: 'form#test', policy_token: repairToken, result: {valid: true}}]}}
    }
    return {data: {objects: [
        {address: 'dashboard#test'},
        {address: 'form#test', policy_token: repairToken},
    ]}}
}
try {
    const r = await form.validate()
    console.log('result:', r)
} catch (e) {
    console.log('error:', e.name, e.code, 'owner:', e.owner)
}
console.log('final token is repair:', form._record.policyToken === repairToken)
