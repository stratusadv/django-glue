import BaseGlueProxy from './base';

/**
 * Proxy for Python callables. Returns a callable function that invokes the
 * server-side function with positional arguments mapped to the function's
 * parameter names.
 */
class GlueFunctionProxy extends BaseGlueProxy {
    static name = 'function';

    /**
     * @param {Object} options - Constructor options.
     * @param {GlueHttp} options.http - The HTTP client instance.
     * @param {string} options.proxyUniqueName - The unique name of this proxy.
     * @param {Object} options.contextData - Serialized proxy metadata from the server.
     */
    constructor({http, proxyUniqueName, contextData}) {
        super({http, proxyUniqueName, contextData});

        /** @type {Array<Object>} */
        this._params = contextData.params || [];
    }

    /**
     * Factory that returns a callable function wrapping the execute action.
     * Positional arguments are mapped to the function's parameter names.
     * @param {Object} options - Constructor options.
     * @param {GlueHttp} options.http - The HTTP client instance.
     * @param {string} options.proxyUniqueName - The unique name of this proxy.
     * @param {Object} options.contextData - Serialized proxy metadata from the server.
     * @returns {Function} A callable that invokes the server-side function.
     */
    static create({http, proxyUniqueName, contextData}) {
        const instance = new GlueFunctionProxy({
            http,
            proxyUniqueName,
            contextData,
        });

        const fn = async function (...args) {
            const payload = {};
            instance._params.forEach((param, i) => {
                if (i < args.length) {
                    payload[param.name] = args[i];
                }
            });

            const response = await instance._processAction('execute', payload);
            return response.result;
        };

        fn._uniqueName = proxyUniqueName;
        fn._contextData = contextData;
        fn._params = instance._params;
        fn.addListener = instance.addListener.bind(instance);
        fn.removeListener = instance.removeListener.bind(instance);
        fn.clearListeners = instance.clearListeners.bind(instance);

        return fn;
    }
}

export default GlueFunctionProxy;
