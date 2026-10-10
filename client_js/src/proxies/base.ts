import type GlueClient from "../client"
import {GlueAddressError, GlueProxyError} from "../errors"
import type {GlueOwnerReference} from "../errors"
import {htmlResultFromResponse} from "../htmlRenderer"
import type GlueHttp from "../http"
import type {GlueAttributeRequest, GlueRequestBatch} from "../http"
import type GluePolicy from "../policy"
import type GlueAddressRecord from "../runtime/addressRecord"
import type {GlueRecordProxy} from "../runtime/addressRecord"
import type GlueAddressRegistry from "../runtime/addressRegistry"
import type {GlueProxyOptions} from "../runtime/addressRegistry"
import type {
    GlueAddressedEntry,
    GlueAttributeCallResponse,
    GlueChildSubmission,
    GlueErrorEntry,
    GlueMessage,
    GlueObjectEntry,
} from "../wire"

interface GlueCallOptions {
    submit?: boolean
    companions?: GlueAddressRecord[]
    batch?: GlueRequestBatch | null
}

// What a proxy adds to its request entries beyond address, token, updates
// and call.
type GlueRequestFields = Pick<GlueAttributeRequest, 'mounted' | 'childSubmissions'>

// What one attempt at a call produced. A discarded attempt is one whose
// address was disposed or reintroduced while the request was in flight.
interface GlueCallOutcome {
    result: unknown
    response: GlueAttributeCallResponse | null
    discarded?: boolean
}

// An event as a listener receives it. `sourceType` is the name it was emitted
// under, which `type` keeps unless a proxy re-delivers it under another.
interface GlueEvent {
    type: string
    sourceType: string
    detail: Record<string, unknown>
    source: BaseGlueProxy
    currentTarget?: BaseGlueProxy
}

type GlueEventListener = (event: GlueEvent) => unknown

type GlueMessageHandler = (context: {messages: GlueMessage[], proxy: BaseGlueProxy}) => void

type GlueErrorHandler = (context: {
    error: unknown
    proxy: BaseGlueProxy
    attribute?: string | null
    attributeRequest?: {attribute: string | null, kwargs: Record<string, unknown>}
    event?: GlueEvent
}) => void

class BaseGlueProxy implements GlueRecordProxy {
    declare _http: GlueHttp
    declare _record: GlueAddressRecord
    declare _registry: GlueAddressRegistry
    declare _client: GlueClient
    declare _owner: GlueRecordProxy | null
    _eventListeners: Map<string, Set<GlueEventListener>>
    _onMessage: GlueMessageHandler | null
    _onError: GlueErrorHandler | null

    constructor({http, record, registry, client, owner = null}: GlueProxyOptions & {owner?: GlueRecordProxy | null}) {
        Object.defineProperties(this, {
            _http: {value: http, enumerable: false, configurable: true},
            _record: {value: record, enumerable: false, configurable: true},
            _registry: {value: registry, enumerable: false, configurable: true},
            _client: {value: client, enumerable: false, configurable: true},
        })
        this._eventListeners = new Map()
        this._onMessage = null
        this._onError = null

        Object.defineProperty(this, '_owner', {
            value: owner,
            writable: true,
            enumerable: false,
            configurable: true,
        })
    }

    get _policy(): GluePolicy {
        return this._record.policy
    }

    get _name(): string {
        return this._record.policy.name
    }

    get $owner(): GlueRecordProxy | null {
        return this._owner
    }

    _requireDeclaredEvent(name: string): void {
        if (!(this._record.staticData?.events || []).includes(name)) {
            throw new GlueProxyError(`Event "${name}" is not declared on this Glue object.`)
        }
    }

    // Raises a declared event from the browser, as if a call had fired it.
    async $dispatch(name: string, detail: Record<string, unknown> = {}): Promise<void> {
        this._requireDeclaredEvent(name)
        this._raiseEvent(name, detail)
    }

    $on(name: string, callback: GlueEventListener): () => boolean {
        this._requireDeclaredEvent(name)
        const listeners = this._eventListeners.get(name) || new Set()
        listeners.add(callback)
        this._eventListeners.set(name, listeners)
        return () => listeners.delete(callback)
    }

    _onDispose(): void {
        this._eventListeners.clear()
    }

    async $refresh({submit = false}: {submit?: boolean} = {}): Promise<this> {
        await this._callAttribute(null, {}, {submit})
        return this
    }

    async _callAttribute(attribute: string | null, kwargs: Record<string, unknown> = {}, options: GlueCallOptions = {}): Promise<unknown> {
        const attributeRequest = {attribute, kwargs}

        return this._record.enqueue(async () => {
            try {
                const {result, discarded} = await this._attempt(attribute, kwargs, options)
                if (discarded) return undefined
                return result
            } catch (error) {
                const errorHandler = this._onError || globalThis.Glue?._onError
                errorHandler?.({error, attribute, attributeRequest, proxy: this})
                throw error
            }
        })
    }

    $dispose(): this {
        const owner = this._record.owner
        if (owner && owner.path !== null) {
            throw new GlueProxyError(
                `address "${this._record.address}" is bound to its owner at path "${owner.path}"; ` +
                'only the owner can remove it (via a successor children map, an effects.dispose, or by disposing the owner).',
            )
        }
        this._registry.dispose(this._record.address)
        return this
    }

    async _attempt(attribute: string | null, kwargs: Record<string, unknown>, options: GlueCallOptions): Promise<GlueCallOutcome> {
        if (this._record.disposed) {
            throw new GlueAddressError(
                'disposed',
                `address "${this._record.address}" has been disposed`,
                this._record.address,
                this._ownerReference(),
            )
        }
        if (this._record.stale) {
            throw this._staleError()
        }
        try {
            return await this._singleCall(attribute, kwargs, options)
        } catch (error) {
            if (!(error instanceof GlueAddressError && error.code === 'policy_expired')) {
                throw error
            }
            if (!await this._reintroduceWithOwner()) {
                this._record.stale = true
                error.owner = this._ownerReference()
                throw error
            }
            return await this._singleCall(attribute, kwargs, options)
        }
    }

    async _singleCall(
        attribute: string | null,
        kwargs: Record<string, unknown>,
        {submit = true, companions = [], batch = null}: GlueCallOptions = {},
    ): Promise<GlueCallOutcome> {
        const requestCapture = this._record.captureRequest()
        if (!submit) requestCapture.updates = {}
        const companionCaptures = companions.map(record => {
            const capture = record.captureRequest()
            capture.updates = {}
            return {record, capture}
        })
        const controller = companions.length ? null : new AbortController()
        this._record.inFlightController = controller
        let response
        try {
            response = await this._http.sendAttributeRequest({
                address: this._record.address,
                policyToken: this._record.policyToken,
                updates: requestCapture.updates,
                attribute,
                kwargs,
                companions,
                signal: controller?.signal ?? null,
                batch,
                ...this._requestFields(attribute),
            })
        } catch (error) {
            if (controller?.signal.aborted && requestCapture.generation !== this._record.generation) {
                return {result: undefined, response: null, discarded: true}
            }
            throw error
        } finally {
            if (this._record.inFlightController === controller) this._record.inFlightController = null
        }
        if (
            this._record.disposed ||
            this._registry.getRecord(this._record.address) !== this._record ||
            requestCapture.generation !== this._record.generation
        ) {
            return {result: undefined, response: response.data, discarded: true}
        }
        const objects = response.data?.objects
        if (!Array.isArray(objects)) {
            throw new GlueProxyError('Glue response is missing the objects envelope.')
        }
        // The entry answering a requested address is never a bare introduction.
        const target = objects.find(entry => entry?.address === this._record.address) as
            GlueAddressedEntry | GlueErrorEntry | undefined
        if (!target) {
            throw new GlueProxyError(
                `Glue response has no entry for address "${this._record.address}".`
            )
        }
        const companionAddresses = new Set(companions.map(record => record.address))
        const introduced = objects.filter(
            entry => entry !== target && !companionAddresses.has(entry?.address),
        ) as GlueObjectEntry[]
        if ('error' in target) {
            throw new GlueAddressError(
                target.error.code,
                target.error.message,
                this._record.address,
                null,
                {status: target.error.status ?? null, details: target.error.details ?? {}},
            )
        }
        if (target.html !== undefined) {
            this._client.loadObjects(introduced)
        } else {
            introduced.forEach(entry => this._registry.introduce(entry))
        }
        companionCaptures.forEach(({record, capture}) => {
            const entry = objects.find(candidate => candidate?.address === record.address)
            if (!entry || 'error' in entry || record.disposed) return
            this._client._dispatcher.reconcile(record.address, entry, capture)
        })
        this._client._dispatcher.reconcile(
            this._record.address,
            target,
            requestCapture,
        )
        const rawResult = target.result
        const result = target.html === undefined
            ? this._convertResult(rawResult, attribute)
            : htmlResultFromResponse(target, this._client)
        await this._applyResponse(target, result)
        if (typeof rawResult === 'string' && this._glueResult(attribute)) {
            const childRecord = this._registry.getRecord(rawResult)
            if (childRecord && !childRecord.owner) {
                childRecord.owner = {address: this._record.address, path: null}
            }
        }
        target.result = result
        this._processEffects(target)
        return {result, response: response.data}
    }

    // Fields this proxy's request entries carry beyond its address, token,
    // updates, and call.
    _requestFields(attribute: string | null): GlueRequestFields {
        return {}
    }

    // What an owner submits for this object when it is the owner's child: its
    // signed token and the changes the user has not saved.
    _submission(): GlueChildSubmission {
        return {
            policy_token: this._record.policyToken,
            updates: this._record.captureRequest().updates,
        }
    }

    // What this proxy does with an accepted response once its state is
    // reconciled and before its effects are processed.
    async _applyResponse(target: GlueAddressedEntry, result: unknown): Promise<void> {}

    async _reintroduceWithOwner(): Promise<boolean> {
        const owner = this._record.owner
        if (!owner?.path) return false
        const ownerProxy = this._registry.getProxy(owner.address)
        const ownerRecord = ownerProxy?._record
        if (!ownerRecord || ownerRecord.stale) return false
        this._record.stale = true
        try {
            const ownerCapture = ownerRecord.captureRequest()
            const response = await this._http.sendAttributeRequest({
                address: owner.address,
                policyToken: ownerRecord.policyToken,
                updates: {},
                reintroduce: [owner.path],
            })
            const objects = response.data?.objects
            if (!Array.isArray(objects)) return false
            const ownerEntry = objects.find(entry => entry?.address === owner.address)
            if (!ownerEntry || 'error' in ownerEntry) return false
            objects
                .filter(entry => entry !== ownerEntry)
                .forEach(entry => this._registry.introduce(entry as GlueObjectEntry))
            this._client._dispatcher.reconcile(owner.address, ownerEntry, ownerCapture)
            return objects.some(entry => entry?.address === this._record.address && !('error' in entry))
        } catch {
            return false
        }
    }

    _staleError(): GlueAddressError {
        const owner = this._ownerReference()
        const slotPath = this._record.owner?.path
        const message = owner
            ? (slotPath !== null
                ? `policy expired; reintroduce it through its owner "${owner.name}" (address "${owner.address}")`
                : `policy expired; this result was produced by "${owner.name}" (address "${owner.address}"); re-run the call that produced it`)
            : 'policy expired; this address cannot be reintroduced through an owner, reload the page or re-run the call that produced it'
        return new GlueAddressError('policy_expired', message, this._record.address, owner)
    }

    _ownerReference(): GlueOwnerReference | null {
        const owner = this._record.owner
        if (!owner) return null
        const ownerProxy = this._registry.getProxy(owner.address)
        return {
            name: ownerProxy?._record.policy.name ?? owner.address,
            address: owner.address,
        }
    }

    _refreshMaterializedInterface(): void {
        this._registry?.refresh(this._record)
    }

    onMessage(callback: GlueMessageHandler | null): this {
        this._onMessage = callback
        return this
    }

    onError(callback: GlueErrorHandler | null): this {
        this._onError = callback
        return this
    }

    _processEffects(entry: Partial<Pick<GlueAddressedEntry, 'effects'>> = {}): void {
        const effects = entry.effects
        if (!effects) return
        const dispose = effects.dispose
        if (dispose?.length) {
            dispose.forEach(address => this._registry.dispose(address))
        }
        const redirect = effects.redirect
        if (redirect?.url && typeof window !== 'undefined') {
            window.location.assign(redirect.url)
        }
        const messages = effects.messages
        if (messages?.length && typeof window !== 'undefined') {
            const handler = this._onMessage || window.Glue?._onMessage
            handler?.({messages, proxy: this})
        }
        effects.events?.forEach(({name, detail}) => this._raiseEvent(name, detail))
    }

    _raiseEvent(name: string, detail: Record<string, unknown>): void {
        this._deliverEvent({
            type: name,
            sourceType: name,
            detail: {...detail, $address: this._record.address},
            source: this,
        })
    }

    _deliverEvent(event: GlueEvent): void {
        const delivered = {...event, currentTarget: this}
        const reportError = (error: unknown) => {
            const handler = this._onError || this._client?._onError
            if (handler) handler({error, event: delivered, proxy: this})
            else console.error(error)
        }
        this._eventListeners.get(event.type)?.forEach(listener => {
            try {
                Promise.resolve(listener(delivered)).catch(reportError)
            } catch (error) {
                reportError(error)
            }
        })
    }

    _convertResult(result: unknown, attribute: string | null = null): unknown {
        if (Array.isArray(result)) {
            return result.map(item => this._convertResult(item, attribute))
        }
        if (typeof result === 'string' && this._glueResult(attribute)) {
            return this._registry.getProxy(result) ?? result
        }
        if (!result || typeof result !== 'object') return result
        const members = result as Record<string, unknown>
        Object.keys(members).forEach(key => {
            members[key] = this._convertResult(members[key], attribute)
        })
        return result
    }

    _glueResult(attribute: string | null): boolean {
        if (!attribute) return false
        return Boolean(this._record.staticData?.callables?.[attribute]?.returns_glue)
    }
}

export type {
    GlueCallOptions,
    GlueCallOutcome,
    GlueErrorHandler,
    GlueEvent,
    GlueEventListener,
    GlueMessageHandler,
    GlueRequestFields,
}
export default BaseGlueProxy
