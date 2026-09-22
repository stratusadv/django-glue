import {reactive} from "../alpine"
import GluePolicy from "../policy"
import {
    applyUpdates,
    assembleAuthoritative,
    cloneValue,
    deriveUpdates,
    mergeComputedData,
    observeValue,
    valuesEqual,
} from "./state"

class GlueAddressRecord {
    constructor({address, policyToken, staticData = {}, computedData = {}, loadingStrategy = 'lazy'}) {
        this.address = address
        this.policyToken = policyToken
        this.policy = GluePolicy.fromSignedPolicyToken(policyToken)
        this.staticData = cloneValue(staticData)
        this.computedData = cloneValue(computedData)
        this.canonical = assembleAuthoritative(this.policy, this.computedData)
        this.editablePaths = new Set()
        this.revisions = new Map()
        this.generation = 0
        this.loadingStrategy = loadingStrategy
        this.owner = null
        this.stale = false
        this.disposed = false
        this.boundChildren = {}
        this.displacedChildren = null
        this.proxy = null
        this._queue = Promise.resolve()
        this._suppressMutations = false
        this.reactiveValues = reactive({})
        this._replaceReactive(this.canonical)
    }

    dispose() {
        this.disposed = true
        this.generation += 1
        this._queue = Promise.resolve()
    }

    attachProxy(proxy) {
        this.proxy = proxy
        proxy._refreshMaterializedInterface()
    }

    setEditablePaths(paths) {
        this.editablePaths = new Set(paths)
        paths.forEach(path => {
            if (!this.revisions.has(path)) this.revisions.set(path, 0)
        })
    }

    getValue(path) {
        return this.reactiveValues[path]
    }

    setValue(path, value) {
        this.reactiveValues[path] = this._observe(path, cloneValue(value))
        if (!this._suppressMutations) this._incrementRevision(path)
    }

    getFieldComputed(path) {
        return this.computedData?.fields?.[path] || {}
    }

    captureRequest() {
        return {
            canonical: cloneValue(this.canonical),
            updates: deriveUpdates(
                this.canonical,
                this.reactiveValues,
                this.editablePaths,
            ),
            revisions: new Map(this.revisions),
            generation: this.generation,
        }
    }

    enqueue(operation) {
        const queued = this._queue.then(operation, operation)
        this._queue = queued.catch(() => undefined)
        return queued
    }

    introduce(entry) {
        if (this.disposed) {
            this.disposed = false
            this.stale = false
            this.generation += 1
            this._queue = Promise.resolve()
        }
        const wasStale = this.stale
        this._applyPolicyToken(entry.policy_token)
        this.staticData = cloneValue(entry.static_data || {})
        this.computedData = cloneValue(entry.computed_data || {})
        this.loadingStrategy = entry.loading_strategy || this.loadingStrategy
        const authoritative = assembleAuthoritative(this.policy, this.computedData)
        const previousCanonical = this.canonical
        this.canonical = authoritative
        this._applyAuthoritative(previousCanonical, authoritative, null)
        if (wasStale) this.generation += 1
        this.proxy?._refreshMaterializedInterface()
    }

    reconcile(entry, requestCapture) {
        if (
            requestCapture?.generation !== undefined &&
            requestCapture.generation !== this.generation
        ) return
        if (entry.policy_token !== undefined) this._applyPolicyToken(entry.policy_token)
        if (entry.static_data !== undefined) this.staticData = cloneValue(entry.static_data || {})
        if (entry.computed_data !== undefined) {
            this.computedData = mergeComputedData(
                this.computedData,
                entry.computed_data || {},
            )
        }

        const authoritative = assembleAuthoritative(this.policy, this.computedData)
        const expected = applyUpdates(requestCapture.canonical, requestCapture.updates)
        this.canonical = authoritative
        this._applyAuthoritative(expected, authoritative, requestCapture)
        this.proxy?._refreshMaterializedInterface()
    }

    _applyPolicyToken(policyToken) {
        const policy = GluePolicy.fromSignedPolicyToken(policyToken)
        if (policy.address !== this.address) {
            throw new Error(`Glue response address "${policy.address}" does not match "${this.address}".`)
        }
        this.policyToken = policyToken
        this.policy = policy
        this.stale = false
    }

    _applyAuthoritative(expected, authoritative, requestCapture) {
        const paths = new Set([
            ...Object.keys(expected || {}),
            ...Object.keys(authoritative || {}),
        ])
        this._suppressMutations = true
        try {
            paths.forEach(path => {
                if (valuesEqual(expected?.[path], authoritative?.[path])) return
                if (this._hasNewerEditableMutation(path, requestCapture, expected)) return
                if (!Object.prototype.hasOwnProperty.call(authoritative, path)) {
                    delete this.reactiveValues[path]
                    return
                }
                this.reactiveValues[path] = this._observe(
                    path,
                    cloneValue(authoritative[path]),
                )
            })
        } finally {
            this._suppressMutations = false
        }
    }

    _hasNewerEditableMutation(path, requestCapture, expected) {
        if (!this.editablePaths.has(path)) return false
        if (requestCapture) {
            return (this.revisions.get(path) || 0) > (requestCapture.revisions.get(path) || 0)
        }
        return !valuesEqual(this.reactiveValues[path], expected?.[path])
    }

    _replaceReactive(values) {
        this._suppressMutations = true
        try {
            Object.keys(this.reactiveValues).forEach(path => delete this.reactiveValues[path])
            Object.entries(values || {}).forEach(([path, value]) => {
                this.reactiveValues[path] = this._observe(path, cloneValue(value))
            })
        } finally {
            this._suppressMutations = false
        }
    }

    _observe(path, value) {
        return observeValue(value, () => {
            if (!this._suppressMutations) this._incrementRevision(path)
        })
    }

    _incrementRevision(path) {
        if (!this.editablePaths.has(path)) return
        this.revisions.set(path, (this.revisions.get(path) || 0) + 1)
    }
}

export default GlueAddressRecord
