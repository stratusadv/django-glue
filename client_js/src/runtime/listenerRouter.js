// Routes a response's events to the mounted ancestors that declared a
// Glue.listener for them (ADR 024). The ancestor chain comes from the source's
// signed identity; each listening ancestor gets one `$receive` call carrying
// its events and the source's current token. Returns the calls' promises.
function deliverToListeners(proxy, entry) {
    const events = entry.effects?.events
    const ancestors = proxy._record.policy.identity?.ancestors
    if (!events?.length || !ancestors?.length) return []

    const eventIds = proxy._record.staticData?.event_ids || {}
    return ancestors.flatMap(address => {
        const ancestor = proxy._registry.getProxy(address)
        if (!ancestor || ancestor._record.disposed || !ancestor.$el) return []
        const listened = new Set(ancestor._record.staticData?.listeners || [])
        const delivered = events
            .filter(({name}) => listened.has(eventIds[name]))
            .map(({name, detail}) => ({
                event: eventIds[name],
                source_token: proxy._record.policyToken,
                detail,
            }))
        return delivered.length ? [ancestor._callAttribute('$receive', {events: delivered})] : []
    })
}

export {deliverToListeners}
