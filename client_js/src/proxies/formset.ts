import type {GlueRecordProxy} from "../runtime/addressRecord"
import type {GlueProxyOptions} from "../runtime/addressRegistry"
import type {GlueChildSubmission, GlueSubmittedForm} from "../wire"
import BaseGlueProxy from "./base"
import type {GlueCallOptions, GlueCallOutcome} from "./base"
import type FieldBackedGlueProxy from "./fieldBacked"

// What FormSetGlue.validate() returns, in
// django_glue/glue/objects/django/formset.py.
interface GlueFormSetValidation {
    valid: boolean
    form_list: unknown[]
    non_form_errors: string[]
}

class GlueFormSetProxy extends BaseGlueProxy {
    nonFormErrors: string[]
    _nextKey: number

    constructor(options: GlueProxyOptions) {
        super(options)
        this.nonFormErrors = []
        this._nextKey = Math.max(
            -1,
            ...Object.keys(this._policy.children || {})
                .map(Number)
                .filter(Number.isSafeInteger),
        ) + 1
    }

    get forms(): GlueRecordProxy[] {
        return Object.entries(this._policy.children || {})
            .map(([, address]) => this._registry.getProxy(address))
            .filter(Boolean) as GlueRecordProxy[]
    }

    get length(): number {
        return this.forms.length
    }

    async append(initial: Record<string, unknown> = {}): Promise<unknown> {
        const key = String(this._nextKey++)
        return await this._callAttribute('append', {key, initial})
    }

    async pop(key: unknown): Promise<GlueRecordProxy | null | undefined> {
        const entry = Object.entries(this._policy.children || {})
            .find(([, address]) => (this._registry.getProxy(address) as FieldBackedGlueProxy | null)?.$key === key)
        if (!entry) return undefined
        const form = this._registry.getProxy(entry[1])
        await this._callAttribute('pop', {key: entry[0]})
        return form
    }

    _singleCall(attribute: string | null, kwargs: Record<string, unknown>, options: GlueCallOptions = {}): Promise<GlueCallOutcome> {
        if (attribute === null || attribute === 'append') {
            return super._singleCall(attribute, kwargs, options)
        }
        // pop submits only the removed row, without its edits: an uncoercible
        // draft value must not block removing the row.
        const forms = attribute === 'pop'
            ? this._submittedForms([kwargs.key as string], false)
            : this._submittedForms()
        return super._singleCall(attribute, {...kwargs, __submitted_forms: forms}, options)
    }

    _submittedForms(
        keys: string[] = Object.keys(this._policy.children || {}),
        withUpdates = true,
    ): Record<string, GlueSubmittedForm> {
        const children = this._policy.children || {}
        return Object.fromEntries(keys.map(key => {
            const record = this._registry.getRecord(children[key])
            if (!record || record.disposed) {
                throw new Error(`Formset row "${key}" is unavailable.`)
            }
            return [key, {
                policy_token: record.policyToken,
                updates: withUpdates ? record.captureRequest().updates : {},
            }]
        }))
    }

    // A formset is submitted with its rows, as its own calls submit them.
    _submission(): GlueChildSubmission {
        return {...super._submission(), forms: this._submittedForms()}
    }

    async validate(): Promise<GlueFormSetValidation | undefined> {
        const result = await this._callAttribute('validate') as GlueFormSetValidation | undefined
        this.nonFormErrors = result?.non_form_errors || []
        return result
    }
}

export default GlueFormSetProxy
