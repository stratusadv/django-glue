import BaseGlueProxy from './base';
import {isObject} from "../utils";

/**
 * Proxy for Python callables. Returns a callable function that invokes the
 * server-side function with keyword arguments (passed in as object fields) mapped to the function's
 * parameter names.
 */
class GlueFunctionProxy extends BaseGlueProxy {
     /**
     * @param {Object} options - Constructor options.
     * @param {GlueHttp} options.http - The HTTP client instance.
     * @param {string} options.name - The unique name of this proxy in the session.
     * @param {Object} options.policy - Proxy policy - immutable and enforces integrity of the proxy.
     * @param {string} options.namespace - Namespace under which this proxy will be accessible in the main Glue instance.
     */
    constructor({http, name, policy, namespace = 'function'}) {
        super({http, name, policy, namespace});

        /** @type {Array<Object>} */
        this._params = policy.subject_details.params || [];
    }

    /**
     * Factory that returns a callable function wrapping the execute bound attribute.
     * Fields inside the single object parameter for the function arguments are mapped to the function's parameter names.
     * @param {Object} options - Constructor options.
     * @param {GlueHttp} options.http - The HTTP client instance.
     * @param {string} options.name - The unique name of this proxy.
     * @param {Object} options.policy - Serialized proxy policy from the server.
     * @returns {Function} A callable that invokes the server-side function.
     */
    static create({http, name, policy}) {
        const instance = new GlueFunctionProxy({
            http,
            name,
            policy,
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

            const response = await instance.execute(payload);
            return response.result;
        };

        fn._name = name;
        fn._policy = policy;
        fn._params = instance._params;
        fn.addListener = instance.addListener.bind(instance);
        fn.removeListener = instance.removeListener.bind(instance);
        fn.clearListeners = instance.clearListeners.bind(instance);
        fn.onMessage = instance.onMessage.bind(instance);

        return fn;
    }
}

export default GlueFunctionProxy;
