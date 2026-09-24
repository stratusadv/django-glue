import {GlueAddressError, GlueProxyError} from "../errors"
import {htmlResultFromResponse, htmlToFragment} from "../htmlRenderer"

class BaseGlueProxy {
    constructor({http, record, registry, client = null, owner = null}) {
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

    get _policy() {
        return this._record.policy
    }

    get _name() {
        return this._record.policy.name
    }

    get $owner() {
        return this._owner
    }

    $on(name, callback) {
        if (!(this._record.staticData?.events || []).includes(name)) {
            throw new GlueProxyError(`Event "${name}" is not declared on this Glue object.`)
        }
        const listeners = this._eventListeners.get(name) || new Set()
        listeners.add(callback)
        this._eventListeners.set(name, listeners)
        return () => listeners.delete(callback)
    }

    _onDispose() {
        this._eventListeners.clear()
    }

    async $refresh({submit = false} = {}) {
        await this._callAttribute(null, {}, {submit})
        return this
    }

    async _callAttribute(attribute, kwargs = {}, options = {}) {
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

    $dispose() {
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

    async _attempt(attribute, kwargs, options) {
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

    async _singleCall(attribute, kwargs, {submit = true, companions = []} = {}) {
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
        const target = objects.find(entry => entry?.address === this._record.address)
        if (!target) {
            throw new GlueProxyError(
                `Glue response has no entry for address "${this._record.address}".`
            )
        }
        const companionAddresses = new Set(companions.map(record => record.address))
        const introduced = objects.filter(
            entry => entry !== target && !companionAddresses.has(entry?.address),
        )
        if (target.error) {
            throw new GlueAddressError(
                target.error.code,
                target.error.message,
                this._record.address
            )
        }
        if (target.html !== undefined) {
            this._client.loadObjects(introduced)
        } else {
            introduced.forEach(entry => this._registry.introduce(entry))
        }
        companionCaptures.forEach(({record, capture}) => {
            const entry = objects.find(candidate => candidate?.address === record.address)
            if (!entry || entry.error || record.disposed) return
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
        // Only HTML rooted at this component's own address (its render(),
        // whether called directly or returned by an action) replaces it. Any
        // other HTML attribute on a component (a modal body, a row) is a
        // fragment for its caller to place.
        if (
            target.html !== undefined
            && this._policy.namespace === 'component'
            && this.$el
            && htmlToFragment(target.html).firstElementChild
                ?.getAttribute('data-glue-address') === this._record.address
        ) {
            await result.renderOuterHtml(this.$el)
        }
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

    async _reintroduceWithOwner() {
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
            if (!ownerEntry || ownerEntry.error) return false
            objects
                .filter(entry => entry !== ownerEntry)
                .forEach(entry => this._registry.introduce(entry))
            this._client._dispatcher.reconcile(owner.address, ownerEntry, ownerCapture)
            return objects.some(entry => entry?.address === this._record.address && !entry.error)
        } catch {
            return false
        }
    }

    _staleError() {
        const owner = this._ownerReference()
        const slotPath = this._record.owner?.path
        const message = owner
            ? (slotPath !== null
                ? `policy expired; reintroduce it through its owner "${owner.name}" (address "${owner.address}")`
                : `policy expired; this result was produced by "${owner.name}" (address "${owner.address}"); re-run the call that produced it`)
            : 'policy expired; this address cannot be reintroduced through an owner, reload the page or re-run the call that produced it'
        return new GlueAddressError('policy_expired', message, this._record.address, owner)
    }

    _ownerReference() {
        const owner = this._record.owner
        if (!owner) return null
        const ownerProxy = this._registry.getProxy(owner.address)
        return {
            name: ownerProxy?._name ?? owner.address,
            address: owner.address,
        }
    }

    _refreshMaterializedInterface() {
        this._registry?.refresh(this._record)
    }

    onMessage(callback) {
        this._onMessage = callback
        return this
    }

    onError(callback) {
        this._onError = callback
        return this
    }

    _processEffects(entry = {}) {
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
        effects.events?.forEach(({name, detail}) => {
            const event = {
                type: name,
                sourceType: name,
                detail: {...detail, $address: this._record.address},
                source: this,
            }
            this._deliverEvent(event)
            let sourcePath = ''
            let descendant = this
            while (descendant._record.owner?.path && descendant._owner) {
                sourcePath = sourcePath
                    ? `${descendant._record.owner.path}.${sourcePath}`
                    : descendant._record.owner.path
                const owner = descendant._owner
                if (owner._record.disposed) break
                Object.entries(owner._record.staticData?.forwarded_events || {})
                    .forEach(([exposedName, fromChild]) => {
                        if (fromChild === `${sourcePath}.${name}`) {
                            owner._deliverEvent({...event, type: exposedName})
                        }
                    })
                descendant = owner
            }
        })
    }

    _deliverEvent(event) {
        const delivered = {...event, currentTarget: this}
        const reportError = error => {
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
        const sourceElement = event.source.$el
        if (
            this.$el
            && typeof CustomEvent !== 'undefined'
            && !(
                this !== event.source
                && event.type === event.sourceType
                && sourceElement
                && this.$el.contains(sourceElement)
            )
        ) {
            const domEvent = new CustomEvent(event.type, {detail: event.detail, bubbles: true})
            domEvent.source = event.source
            this.$el.dispatchEvent(domEvent)
        }
    }

    _convertResult(result, attribute = null) {
        if (Array.isArray(result)) {
            return result.map(item => this._convertResult(item, attribute))
        }
        if (typeof result === 'string' && this._glueResult(attribute)) {
            return this._registry.getProxy(result) ?? result
        }
        if (!result || typeof result !== 'object') return result
        Object.keys(result).forEach(key => {
            result[key] = this._convertResult(result[key], attribute)
        })
        return result
    }

    _glueResult(attribute) {
        if (!attribute) return false
        return Boolean(this._record.staticData?.callables?.[attribute]?.returns_glue)
    }
}

export default BaseGlueProxy
