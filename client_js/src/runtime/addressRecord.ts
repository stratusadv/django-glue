import {reactive} from "../alpine"
import GluePolicy from "../policy"
import type FieldGlue from "../proxies/fields/base"
import type {
    GlueAddressedEntry,
    GlueChildSubmission,
    GlueComputedData,
    GlueFieldComputed,
    GlueObjectEntry,
    GlueStaticData,
} from "../wire"
import {
    applyUpdates,
    assembleAuthoritative,
    cloneValue,
    deriveUpdates,
    mergeComputedData,
    observeValue,
    valuesEqual,
} from "./state"
import type {GlueValues} from "./state"

// What the runtime needs of the proxy a record holds. The proxy classes
// implement it; the runtime depends on nothing else of theirs.
interface GlueRecordProxy {
    _record: GlueAddressRecord
    _owner: GlueRecordProxy | null
    _fields?: Record<string, FieldGlue>
    _refreshMaterializedInterface(): void
    _afterRecordRefresh?(): void
    _onDispose?(): void
    _callAttribute(attribute: string | null, kwargs?: Record<string, unknown>): Promise<unknown>
    _submission(): GlueChildSubmission
}

// Where a record sits under its owner. A null path means the owner produced
// it as a call's result rather than holding it in a child slot.
interface GlueRecordOwner {
    address: string
    path: string | null
}

// A record's state as a request left with it, kept to reconcile the response.
interface GlueRequestCapture {
    canonical: GlueValues
    updates: GlueValues
    revisions: Map<string, number>
    generation: number
}

// The parts of a response entry a record reconciles; each is omitted when
// unchanged.
type GlueReconcileEntry = Partial<Pick<GlueAddressedEntry, 'policy_token' | 'static_data' | 'computed_data'>>

class GlueAddressRecord {
    address: string
    policyToken: string
    policy: GluePolicy
    staticData: GlueStaticData
    computedData: GlueComputedData
    receivedComputedData: GlueComputedData | null
    canonical: GlueValues
    editablePaths: Set<string>
    revisions: Map<string, number>
    generation: number
    owner: GlueRecordOwner | null
    stale: boolean
    disposed: boolean
    boundChildren: Record<string, string>
    displacedChildren: string[] | null
    proxy: GlueRecordProxy | null
    _queue: Promise<unknown>
    inFlightController: AbortController | null
    _suppressMutations: boolean
    reactiveValues: GlueValues

    constructor({address, policyToken, staticData = {}, computedData = {}}: {
        address: string
        policyToken: string
        staticData?: GlueStaticData
        computedData?: GlueComputedData
    }) {
        this.address = address
        this.policyToken = policyToken
        this.policy = GluePolicy.fromSignedPolicyToken(policyToken)
        this.staticData = cloneValue(staticData)
        this.computedData = cloneValue(computedData)
        this.receivedComputedData = computedData
        this.canonical = assembleAuthoritative(this.policy, this.computedData)
        this.editablePaths = new Set()
        this.revisions = new Map()
        this.generation = 0
        this.owner = null
        this.stale = false
        this.disposed = false
        this.boundChildren = {}
        this.displacedChildren = null
        this.proxy = null
        this._queue = Promise.resolve()
        this.inFlightController = null
        this._suppressMutations = false
        this.reactiveValues = reactive({})
        this._replaceReactive(this.canonical)
    }

    dispose(): void {
        this.disposed = true
        this.generation += 1
        this._queue = Promise.resolve()
        this.inFlightController?.abort()
        this.inFlightController = null
    }

    attachProxy(proxy: GlueRecordProxy): void {
        this.proxy = proxy
        proxy._refreshMaterializedInterface()
    }

    setEditablePaths(paths: string[]): void {
        this.editablePaths = new Set(paths)
        paths.forEach(path => {
            if (!this.revisions.has(path)) this.revisions.set(path, 0)
        })
    }

    getValue(path: string): unknown {
        return this.reactiveValues[path]
    }

    setValue(path: string, value: unknown): void {
        this.reactiveValues[path] = this._observe(path, cloneValue(value))
        if (!this._suppressMutations) this._incrementRevision(path)
    }

    getFieldComputed(path: string): Partial<GlueFieldComputed> {
        return this.computedData?.fields?.[path] || {}
    }

    captureRequest(): GlueRequestCapture {
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

    enqueue<T>(operation: () => Promise<T>): Promise<T> {
        const queued = this._queue.then(operation, operation)
        this._queue = queued.catch(() => undefined)
        return queued
    }

    introduce(entry: GlueObjectEntry): void {
        const wasStale = this.stale
        this._applyPolicyToken(entry.policy_token)
        this.staticData = cloneValue(entry.static_data || {})
        this.computedData = cloneValue(entry.computed_data || {})
        this.receivedComputedData = entry.computed_data ?? null
        const authoritative = assembleAuthoritative(this.policy, this.computedData)
        const previousCanonical = this.canonical
        this.canonical = authoritative
        this._applyAuthoritative(previousCanonical, authoritative, null)
        if (wasStale) this.generation += 1
        this.proxy?._refreshMaterializedInterface()
    }

    reconcile(entry: GlueReconcileEntry, requestCapture: GlueRequestCapture): void {
        if (
            requestCapture?.generation !== undefined &&
            requestCapture.generation !== this.generation
        ) return
        if (entry.policy_token !== undefined) this._applyPolicyToken(entry.policy_token)
        if (entry.static_data !== undefined) this.staticData = cloneValue(entry.static_data || {})
        this.receivedComputedData = entry.computed_data ?? null
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

    _applyPolicyToken(policyToken: string): void {
        const policy = GluePolicy.fromSignedPolicyToken(policyToken)
        if (policy.address !== this.address) {
            throw new Error(`Glue response address "${policy.address}" does not match "${this.address}".`)
        }
        this.policyToken = policyToken
        this.policy = policy
        this.stale = false
    }

    _applyAuthoritative(expected: GlueValues, authoritative: GlueValues, requestCapture: GlueRequestCapture | null): void {
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

    _hasNewerEditableMutation(path: string, requestCapture: GlueRequestCapture | null, expected: GlueValues): boolean {
        if (!this.editablePaths.has(path)) return false
        if (requestCapture) {
            return (this.revisions.get(path) || 0) > (requestCapture.revisions.get(path) || 0)
        }
        return !valuesEqual(this.reactiveValues[path], expected?.[path])
    }

    _replaceReactive(values: GlueValues): void {
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

    _observe<T>(path: string, value: T): T {
        return observeValue(value, () => {
            if (!this._suppressMutations) this._incrementRevision(path)
        })
    }

    _incrementRevision(path: string): void {
        if (!this.editablePaths.has(path)) return
        this.revisions.set(path, (this.revisions.get(path) || 0) + 1)
    }
}

export type {GlueReconcileEntry, GlueRecordOwner, GlueRecordProxy, GlueRequestCapture}
export default GlueAddressRecord
