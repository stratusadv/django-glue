import type {GlueProxyOptions} from "../runtime/addressRegistry"
import type {GlueStaticData} from "../wire"
import BaseGlueProxy from "./base"

// A parameter as FunctionGlue._params_for() describes it, in
// django_glue/glue/function.py.
interface GlueFunctionParam {
    name: string
    type: string | null
}

// FunctionGlue.get_static_data() adds the function's parameters.
interface GlueFunctionStaticData extends GlueStaticData {
    params?: (string | GlueFunctionParam)[]
}

class GlueFunctionProxy extends BaseGlueProxy {
    // The proxy is callable: calling it executes the function, and every
    // other member reads through to the GlueFunctionProxy behind it.
    static create(options: GlueProxyOptions): GlueFunctionProxy {
        const object = new GlueFunctionProxy(options)
        const members = object as unknown as Record<string | symbol, unknown>
        const callable = async (kwargs: Record<string, unknown> = {}) => await object.execute(kwargs)

        return new Proxy(callable, {
            get(target, prop) {
                if (prop in object) {
                    const value = members[prop]
                    return typeof value === 'function' ? value.bind(object) : value
                }
                return (target as unknown as Record<string | symbol, unknown>)[prop]
            },
            set(target, prop, value) {
                members[prop] = value
                return true
            },
        }) as unknown as GlueFunctionProxy
    }

    async execute(kwargs: Record<string, unknown> = {}): Promise<unknown> {
        const result = await this._callAttribute('execute', this._filterKwargs(kwargs)) as {result?: unknown} | null | undefined
        return result?.result ?? result
    }

    _filterKwargs(kwargs: Record<string, unknown>): Record<string, unknown> {
        const params = this._normalizeParams((this._record.staticData as GlueFunctionStaticData).params || [])
        if (!params.length) {
            return kwargs
        }

        return Object.fromEntries(
            Object.entries(kwargs).filter(([key]) => params.includes(key))
        )
    }

    _normalizeParams(params: (string | GlueFunctionParam)[]): string[] {
        return params.map(param => typeof param === 'string' ? param : param.name).filter(Boolean)
    }
}

export default GlueFunctionProxy
