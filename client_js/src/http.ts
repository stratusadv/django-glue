import type GlueConfig from "./config"
import {GlueHttpError} from "./errors"
import {serializeValue, shouldJsonSerializePostData} from "./utils"
import type {GlueAttributeCallResponse, GlueErrorData, GlueRequestEntry, GlueResponseEntry} from "./wire"

interface GlueRequestOptions {
    method?: string
    headers?: Record<string, string>
    contentType?: string | null
    payload?: unknown
    body?: unknown
    csrfProtected?: boolean
    timeoutSeconds?: number
    signal?: AbortSignal | null
}

interface GlueHttpResponse<TData = unknown> {
    ok: boolean
    payload: string
    httpResponse: Response
    data: TData | null
}

type GlueFileValue = File | Blob | FileList | (File | Blob)[]

// Another address refreshed in the same request as the one being called.
interface GlueCompanion {
    address: string
    policyToken: string
}

interface GlueAttributeRequest {
    address: string
    policyToken: string
    updates?: Record<string, unknown>
    attribute?: string | null
    kwargs?: Record<string, unknown>
    reintroduce?: string[] | null
    companions?: GlueCompanion[]
    mounted?: string[]
    signal?: AbortSignal | null
    batch?: GlueRequestBatch | null
}

type GlueAttributeResponse = GlueHttpResponse<GlueAttributeCallResponse>

class GlueHttp {
    _config: GlueConfig

    constructor(config: GlueConfig) {
        this._config = config
    }

    getCookie(name: string): string | null {
        if (document?.cookie !== '') {
            const cookies = document.cookie.split(';').map(cookie => cookie.trim())
            for (const cookie of cookies) {
                if (cookie.substring(0, name.length + 1) === `${name}=`) {
                    return decodeURIComponent(cookie.substring(name.length + 1))
                }
            }
        }
        return null
    }

    async sendRequest<TData = unknown>(url: string, requestOptions: GlueRequestOptions = {}): Promise<GlueHttpResponse<TData>> {
        const timeoutSeconds = requestOptions.timeoutSeconds ?? this._config.requestTimeoutSeconds
        const controller = new AbortController()
        const timeoutId = setTimeout(() => controller.abort(), timeoutSeconds * 1000)
        requestOptions.signal?.addEventListener('abort', () => controller.abort(), {once: true})
        const headers: Record<string, string | null> = {...(requestOptions.headers || {})}
        const method = requestOptions.method || 'GET'
        let contentType = requestOptions.contentType
        let payload = requestOptions.payload ?? requestOptions.body
        let csrfProtected = requestOptions.csrfProtected

        if (method === 'GET') {
            contentType = null
            payload = null
            csrfProtected = false
        }

        if (contentType && contentType !== 'multipart/form-data') {
            headers['Content-Type'] = contentType
        }

        if (contentType === 'application/json' && payload) {
            payload = shouldJsonSerializePostData(payload) ?
                JSON.stringify(payload) :
                payload
        }

        if (csrfProtected !== false) {
            headers['X-CSRFToken'] = this.getCookie(this._config.csrfCookieName)
        }

        try {
            const response = await fetch(url, {
                method,
                body: payload as BodyInit | null | undefined,
                // fetch sends a header whose value is null as the text "null".
                headers: headers as Record<string, string>,
                signal: controller.signal,
            })

            if (!response.ok) {
                throw await this._buildRequestError(response)
            }

            const isJson = (response.headers.get('Content-Type') || '').includes('json')
            return {
                ok: response.ok,
                payload: await response.clone().text(),
                httpResponse: response,
                data: isJson ? await response.json() : null,
            }
        } finally {
            clearTimeout(timeoutId)
        }
    }

    async get<TData = unknown>(url: string, params?: unknown, headers: Record<string, string> = {}) {
        return await this.sendRequest<TData>(url, {
            payload: params,
            headers: headers,
        })
    }

    async postJson<TData = unknown>(url: string, data: unknown, headers: Record<string, string> = {}, csrfProtected = true) {
        return await this.sendRequest<TData>(url, {
            payload: data,
            method: 'POST',
            headers: headers,
            contentType: 'application/json',
            csrfProtected,
        })
    }

    async postForm<TData = unknown>(
        url: string,
        data: FormData,
        headers: Record<string, string> = {},
        csrfProtected = true,
        signal: AbortSignal | null = null,
    ) {
        return await this.sendRequest<TData>(url, {
            payload: data,
            method: 'POST',
            contentType: 'multipart/form-data',
            headers: headers,
            csrfProtected,
            signal,
        })
    }

    async sendAttributeRequest({
        address,
        policyToken,
        updates = {},
        attribute = null,
        kwargs = {},
        reintroduce = null,
        companions = [],
        mounted = [],
        signal = null,
        batch = null,
    }: GlueAttributeRequest): Promise<GlueAttributeResponse> {
        const {files, data} = this._extractFiles(serializeValue(updates) as Record<string, unknown>)

        const entry: GlueRequestEntry = {
            address,
            policy_token: policyToken,
            updates: data,
        }
        if (attribute !== null) entry.call = {attribute, kwargs}
        if (reintroduce) entry.reintroduce = reintroduce
        if (mounted.length) entry.mounted = mounted
        const entries = [entry, ...companions.map(companion => ({
            address: companion.address,
            policy_token: companion.policyToken,
            updates: {},
        }))]

        // A request with files travels alone, as does one its batch refuses.
        if (!batch?.accepts(entries) || Object.keys(files).length) {
            return await this._postEntries(entries, files, signal)
        }
        return await batch.add(entries)
    }

    async _postEntries(
        entries: GlueRequestEntry[],
        files: Record<string, GlueFileValue>,
        signal: AbortSignal | null,
    ): Promise<GlueAttributeResponse> {
        const formData = new FormData()
        formData.append('objects', JSON.stringify(entries))

        Object.entries(files).forEach(([key, value]) => {
            if (value instanceof FileList) {
                Array.from(value).forEach(file => formData.append(key, file))
            } else if (Array.isArray(value)) {
                value.forEach(file => formData.append(key, file))
            } else {
                formData.append(key, value)
            }
        })

        return await this.postForm(this._config.attributeUrlPath, formData, {}, true, signal)
    }

    _extractFiles(obj: Record<string, unknown> | null | undefined) {
        const files: Record<string, GlueFileValue> = {}
        const data: Record<string, unknown> = {}

        const isFileValue = (value: unknown): value is File | Blob | FileList =>
            value instanceof File ||
            value instanceof Blob ||
            value instanceof FileList

        const extractFromValue = (value: unknown, key: string): unknown => {
            if (isFileValue(value)) {
                files[key] = value
                return undefined
            }

            if (Array.isArray(value)) {
                const hasFiles = value.some(item => item instanceof File || item instanceof Blob)
                if (!hasFiles) {
                    return value
                }
                files[key] = value.filter(item => item instanceof File || item instanceof Blob)
                const nonFiles = value.filter(item => !(item instanceof File || item instanceof Blob))
                return nonFiles.length > 0 ? nonFiles : undefined
            }

            if (value && typeof value === 'object') {
                const nested = this._extractFiles(value as Record<string, unknown>)
                Object.entries(nested.files).forEach(([nestedKey, fileValue]) => {
                    files[`${key}.${nestedKey}`] = fileValue
                })
                return Object.keys(nested.data).length > 0 ? nested.data : undefined
            }

            return value
        }

        Object.entries(obj || {}).forEach(([key, value]) => {
            const wrapped = value && typeof value === 'object' ? (value as {value?: unknown}).value : undefined
            if (isFileValue(wrapped)) {
                files[key] = wrapped
                return
            }

            const extracted = extractFromValue(value, key)
            if (extracted !== undefined) {
                data[key] = extracted
            }
        })

        return {files, data}
    }

    async _buildRequestError(response: Response): Promise<GlueHttpError> {
        const body = await response.text()
        let payload: {result?: {error?: GlueErrorData}, error?: GlueErrorData} | null = null

        try {
            payload = JSON.parse(body)
        } catch (_) {
            // Non-Glue failures may still be plain text.
        }

        const errorData = payload?.result?.error || payload?.error
        return new GlueHttpError({
            message: errorData?.message || body,
            status: response.status,
            code: errorData?.code,
            payload: errorData || null,
            responseBody: body,
        })
    }
}

interface GluePendingRequest {
    entries: GlueRequestEntry[]
    resolve: (response: GlueAttributeResponse) => void
    reject: (error: unknown) => void
}

// Collects up to `size` attribute requests into one POST and hands each
// caller its own share of the response (ADR 025). It sends when the last
// request arrives, or on the next task if some never do.
class GlueRequestBatch {
    _http: GlueHttp
    _size: number
    _pending: GluePendingRequest[]
    _timer: ReturnType<typeof setTimeout> | null
    _sent: boolean

    constructor(http: GlueHttp, size: number) {
        this._http = http
        this._size = size
        this._pending = []
        this._timer = null
        this._sent = false
    }

    // A batch takes no request after it is sent, and never two entries for
    // one address, which the endpoint rejects as a whole.
    accepts(entries: GlueRequestEntry[]): boolean {
        if (this._sent) return false
        const addresses = new Set(this._pending.flatMap(item => item.entries.map(entry => entry.address)))
        return entries.every(entry => !addresses.has(entry.address))
    }

    add(entries: GlueRequestEntry[]): Promise<GlueAttributeResponse> {
        return new Promise((resolve, reject) => {
            this._pending.push({entries, resolve, reject})
            if (this._pending.length >= this._size) this._send()
            else this._timer ??= setTimeout(() => this._send(), 0)
        })
    }

    async _send() {
        if (this._timer !== null) clearTimeout(this._timer)
        this._sent = true
        const pending = this._pending
        try {
            const response = await this._http._postEntries(pending.flatMap(item => item.entries), {}, null)
            // The response lists each requested entry followed by the
            // children it introduced; hand each caller its own run.
            const owners = new Map(pending.flatMap((item, index) => (
                item.entries.map((entry): [string, number] => [entry.address, index])
            )))
            const shares: GlueResponseEntry[][] = pending.map(() => [])
            let owner = 0
            ;(response.data?.objects || []).forEach(object => {
                owner = owners.get(object?.address) ?? owner
                shares[owner].push(object)
            })
            pending.forEach((item, index) => item.resolve({
                ...response,
                data: {...response.data, objects: shares[index]},
            }))
        } catch (error) {
            pending.forEach(item => item.reject(error))
        }
    }
}

export type {GlueAttributeRequest, GlueAttributeResponse, GlueCompanion, GlueHttpResponse, GlueRequestOptions}
export {GlueRequestBatch}
export default GlueHttp
