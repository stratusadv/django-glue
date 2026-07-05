import BaseGlueProxy from './base';
import {isObject} from "../utils";

/**
 * Proxy for Python callables. Returns a callable function that invokes the
 * server-side function with keyword arguments (passed in as object fields) mapped to the function's
 * parameter names.
 */
class GlueFunctionProxy extends BaseGlueProxy {
    static name = 'function';

    /**
     * @param {Object} options - Constructor options.
     * @param {GlueHttp} options.http - The HTTP client instance.
     * @param {string} options.proxyUniqueName - The unique name of this proxy.
     * @param {Object} options.contract - Serialized proxy metadata from the server.
     */
    constructor({http, proxyUniqueName, contract}) {
        super({http, proxyUniqueName, contract});

        /** @type {Array<Object>} */
        this._params = contract.params || [];
    }

    /**
     * Factory that returns a callable function wrapping the execute action.
     * Fields inside the single object parameter for the function arguments are mapped to the function's parameter names.
     * @param {Object} options - Constructor options.
     * @param {GlueHttp} options.http - The HTTP client instance.
     * @param {string} options.proxyUniqueName - The unique name of this proxy.
     * @param {Object} options.contract - Serialized proxy metadata from the server.
     * @returns {Function} A callable that invokes the server-side function.
     */
    static create({http, name, contract}) {
        const instance = new GlueFunctionProxy({
            http,
            name,
            contract,
        });

        const fn = async function (kwargs = {}) {
            if (!isObject(kwargs)) {
                throw Error('Must pass glue function arguments as fields in an object.')
            }

            const payload = {};
            instance._params.forEach(param => {
                if (param.name in kwargs) {
                    payload[param.name] = kwargs[param.name]
                }
            });

            const response = await instance._processAction('execute', payload);
            return response.result;
        };

        fn._name = name;
        fn._contract = contract;
        fn._params = instance._params;
        fn.addListener = instance.addListener.bind(instance);
        fn.removeListener = instance.removeListener.bind(instance);
        fn.clearListeners = instance.clearListeners.bind(instance);

        return fn;
    }
}

export default GlueFunctionProxy;
