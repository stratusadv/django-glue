import {GlueRequestBatch} from "../http"

// Routes a response's events to the components that react to them (ADR 024,
// ADR 025): a mounted component that lists the event in `rerender_on`,
// anywhere on the page, and a mounted ancestor with a `Glue.listener` for it.
// The ancestor chain comes from the source's signed identity. Every reacting
// component gets one `$receive` call with its events and the source's current
// token, and all of them travel in one request. Returns the calls' promises.
function deliverToListeners(proxy, entry) {
    const events = entry.effects?.events
    if (!events?.length) return []

    const eventIds = proxy._record.staticData?.event_ids || {}
    const ancestors = new Set(proxy._record.policy.identity?.ancestors || [])
    const deliveries = []
    proxy._registry.records.forEach(record => {
        if (record === proxy._record || record.disposed || !record.proxy?.$el) return
        const reacting = new Set([
            ...(record.staticData?.rerender_on || []),
            ...(ancestors.has(record.address) ? record.staticData?.listeners || [] : []),
        ])
        const delivered = events
            .filter(({name}) => reacting.has(eventIds[name]))
            .map(({name, detail}) => ({
                event: eventIds[name],
                source_token: proxy._record.policyToken,
                detail,
            }))
        if (delivered.length) deliveries.push([record.proxy, delivered])
    })
    if (!deliveries.length) return []

    const batch = new GlueRequestBatch(proxy._http, deliveries.length)
    return deliveries.map(([recipient, delivered]) => (
        recipient._callAttribute('$receive', {events: delivered}, {batch})
    ))
}

export {deliverToListeners}
