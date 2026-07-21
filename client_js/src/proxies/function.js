import BaseGlueProxy from "./base"

class GlueFunctionProxy extends BaseGlueProxy {
    static create(options) {
        const object = new GlueFunctionProxy(options)
        const callable = async (kwargs = {}) => await object.execute(kwargs)

        return new Proxy(callable, {
            get(target, prop) {
                if (prop in object) {
                    const value = object[prop]
                    return typeof value === 'function' ? value.bind(object) : value
                }
                return target[prop]
            },
            set(target, prop, value) {
                object[prop] = value
                return true
            },
        })
    }

    async execute(kwargs = {}) {
        const result = await this._callAttribute('execute', this._filterKwargs(kwargs))
        return result?.result ?? result
    }

    _filterKwargs(kwargs) {
        const params = this._normalizeParams(this._metadata?.params || this._policy?.identity?.params || [])
        if (!params.length) {
            return kwargs
        }

        return Object.fromEntries(
            Object.entries(kwargs).filter(([key]) => params.includes(key))
        )
    }

    _normalizeParams(params) {
        return params.map(param => typeof param === 'string' ? param : param.name).filter(Boolean)
    }
}

export default GlueFunctionProxy
