import BaseGlueProxy from "./base"
import type {GlueEvent} from "./base"
import HtmlRenderer, {htmlToFragment} from "../htmlRenderer"
import type {HtmlResult} from "../htmlRenderer"
import {GlueRequestBatch} from "../http"
import type {GlueAddressedEntry, GlueStaticData} from "../wire"

// Component.get_static_data() in django_glue/glue/components/component.py
// adds each declared event's identity and the identities the component
// re-renders on and listens for.
interface GlueComponentStaticData extends GlueStaticData {
    event_ids?: Record<string, string>
    rerender_on?: string[]
    listeners?: string[]
}

// An event as `$receive` takes it: its identity, the emitter's token and the
// detail it was emitted with.
interface GlueReceivedEvent {
    event: string
    source_token: string
    detail: Record<string, unknown>
}

class GlueComponentProxy extends HtmlRenderer(BaseGlueProxy) {
    get $el(): Element | null {
        if (this._record.disposed || typeof document === 'undefined') return null
        return [...document.querySelectorAll('[data-glue-address]')].find(
            element => element.getAttribute('data-glue-address') === this._record.address
        ) || null
    }

    async _getHtml(payload: Record<string, unknown> = {}): Promise<string | null> {
        const result = await this._callAttribute('render', payload) as {html?: string | null} | string | null
        return (result as {html?: string | null} | null)?.html ?? (result as string | null)
    }

    // A render keeps the children still mounted in this component (ADR 025).
    _requestFields(): {mounted?: string[]} {
        const root = this.$el
        if (!root) return {}
        return {
            mounted: [...root.querySelectorAll('[data-glue-address]')].map(
                element => element.getAttribute('data-glue-address')!,
            ),
        }
    }

    // A rendered component also dispatches its events as bubbling DOM events
    // from its root, unless the event is bubbling up from a descendant's root
    // inside this one, where the browser already carries it.
    _deliverEvent(event: GlueEvent): void {
        super._deliverEvent(event)
        const root = this.$el
        const sourceElement = (event.source as BaseGlueProxy & {$el?: Element | null}).$el
        if (
            root
            && typeof CustomEvent !== 'undefined'
            && !(
                this !== event.source
                && event.type === event.sourceType
                && sourceElement
                && root.contains(sourceElement)
            )
        ) {
            const domEvent: CustomEvent & {source?: BaseGlueProxy} = new CustomEvent(event.type, {detail: event.detail, bubbles: true})
            domEvent.source = event.source
            root.dispatchEvent(domEvent)
        }
    }

    // Calls `$receive` on every component that reacts to this response's
    // events (ADR 024, ADR 025): any mounted component that re-renders on one,
    // anywhere on the page, and any mounted ancestor with a listener for one.
    // The calls travel in one request. Returns their promises.
    _deliverEvents(target: GlueAddressedEntry): Promise<unknown>[] {
        const eventIds = (this._record.staticData as GlueComponentStaticData)?.event_ids || {}
        const events = (target.effects?.events || [])
            .filter(({name}) => eventIds[name])
            .map(({name, detail}): GlueReceivedEvent => ({
                event: eventIds[name],
                source_token: this._record.policyToken,
                detail,
            }))
        if (!events.length) return []

        const ancestors = new Set(this._record.policy.identity?.ancestors || [])
        const mounted = [...this._registry.records.values()]
            .map(record => record.proxy)
            .filter(proxy => proxy instanceof GlueComponentProxy && proxy !== this && proxy.$el) as GlueComponentProxy[]
        const deliveries = mounted
            .map((proxy): [GlueComponentProxy, GlueReceivedEvent[]] => [proxy, proxy._reactionsTo(events, ancestors.has(proxy._record.address))])
            .filter(([, reactions]) => reactions.length)
        if (!deliveries.length) return []

        const batch = new GlueRequestBatch(this._http, deliveries.length)
        return deliveries.map(([proxy, reactions]) => (
            proxy._callAttribute('$receive', {events: reactions}, {batch})
        ))
    }

    // The events this component reacts to: those it re-renders on, and those
    // it listens for when they come from one of its descendants.
    _reactionsTo(events: GlueReceivedEvent[], fromDescendant: boolean): GlueReceivedEvent[] {
        const staticData: GlueComponentStaticData = this._record.staticData || {}
        const reacting = new Set([
            ...(staticData.rerender_on || []),
            ...(fromDescendant ? staticData.listeners || [] : []),
        ])
        return events.filter(({event}) => reacting.has(event))
    }

    async _applyResponse(target: GlueAddressedEntry, result: unknown): Promise<void> {
        // Components reacting to this response's events re-render too, so
        // this component's own morph waits for them and the page changes once.
        await Promise.allSettled(this._deliverEvents(target))
        // Only HTML rooted at this component's own address (its render(),
        // whether called directly or returned by an action) replaces it. Any
        // other HTML attribute on a component (a modal body, a row) is a
        // fragment for its caller to place.
        if (
            target.html !== undefined
            && this.$el
            && htmlToFragment(target.html).firstElementChild
                ?.getAttribute('data-glue-address') === this._record.address
        ) {
            await (result as HtmlResult).renderOuterHtml(this.$el)
        }
    }
}

export default GlueComponentProxy
