import {GlueAddressError, GlueProxyError} from "../errors"
import {htmlResultFromResponse} from "../htmlRenderer"

class BaseGlueProxy {
    constructor({http, record, registry, client = null, owner = null}) {
        Object.defineProperties(this, {
            _http: {value: http, enumerable: false, configurable: true},
            _record: {value: record, enumerable: false, configurable: true},
            _registry: {value: registry, enumerable: false, configurable: true},
            _client: {value: client, enumerable: false, configurable: true},
        })
        this._listeners = {before: {}, after: {}, error: {}}
        this._onMessage = null
        this._onError = null
        this._loaded = record.loadingStrategy === 'eager'

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

    addListener(attribute, callback, when = 'after') {
        this._listeners[when] ||= {}
        this._listeners[when][attribute] ||= []
        this._listeners[when][attribute].push(callback)
        return this
    }

    removeListener(attribute, callback, when = 'after') {
        const listeners = this._listeners[when]?.[attribute]
        if (listeners) {
            this._listeners[when][attribute] = listeners.filter(listener => listener !== callback)
        }
        return this
    }

    async _callAttribute(attribute, kwargs = {}) {
        const attributeRequest = {attribute, kwargs}
        this._emit('before', attribute, {attributeRequest, object: this})

        return this._record.enqueue(async () => {
            try {
                const {result, response, discarded} = await this._attempt(attribute, kwargs)
                if (discarded) return undefined
                this._emit('after', attribute, {
                    attributeRequest,
                    object: this,
                    proxy: this,
                    response,
                })
                return result
            } catch (error) {
                this._emit('error', attribute, {attributeRequest, object: this, proxy: this, error})
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

    async _attempt(attribute, kwargs) {
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
            return await this._singleCall(attribute, kwargs)
        } catch (error) {
            if (!(error instanceof GlueAddressError && error.code === 'policy_expired')) {
                throw error
            }
            if (!await this._reintroduceWithOwner()) {
                this._record.stale = true
                error.owner = this._ownerReference()
                throw error
            }
            return await this._singleCall(attribute, kwargs)
        }
    }

    async _singleCall(attribute, kwargs) {
        const requestCapture = this._record.captureRequest()
        const response = await this._http.sendAttributeRequest({
            address: this._record.address,
            policyToken: this._record.policyToken,
            updates: requestCapture.updates,
            attribute,
            kwargs,
        })
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
        objects
            .filter(entry => entry !== target)
            .forEach(entry => this._registry.introduce(entry))
        if (target.error) {
            throw new GlueAddressError(
                target.error.code,
                target.error.message,
                this._record.address
            )
        }
        this._client._dispatcher.reconcile(
            this._record.address,
            target,
            requestCapture,
        )
        const rawResult = target.result
        const result = this._convertResult(rawResult, attribute)
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
        if (!messages?.length || typeof window === 'undefined') return
        const handler = this._onMessage || window.Glue?._onMessage
        handler?.({messages, proxy: this})
    }

    _emit(when, attribute, payload) {
        const listeners = [
            ...(this._listeners[when]?.[attribute] || []),
            ...(this._listeners[when]?.['*'] || []),
        ]
        listeners.forEach(listener => listener(payload))
    }

    _convertResult(result, attribute = null) {
        if (Array.isArray(result)) {
            return result.map(item => this._convertResult(item, attribute))
        }
        if (typeof result === 'string' && this._glueResult(attribute)) {
            return this._registry.getProxy(result) ?? result
        }
        if (!result || typeof result !== 'object') return result
        if (result.is_glue_manifest === true) return this._client.resolveManifest(result)
        if (result.is_glue_template_response === true) {
            return htmlResultFromResponse(result, this._client)
        }
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
