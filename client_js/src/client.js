import GlueHttp from "./http";
import {SUBJECT_TYPE_TO_PROXY_CLASS as PROXY_NAMESPACE_TO_PROXY_CLASS} from "./proxies";
import GlueView from "./view";

/**
 * Main Django Glue client. Manages proxy initialization, keep-alive polling,
 * and provides the public API for model, queryset, and form proxies.
 */
class GlueClient {
    /** @type {Object} */
    static proxies = {}
    /** @type {Object} */
    static proxyClassesForSubjectTypes = {}

    /** @type {Object} */
    model = {}
    /** @type {Object} */
    querySet = {}
    /** @type {Object} */
    form = {}
    /** @type {Object} */
    template = {}
    /** @type {Object} */
    function = {}

    /**
     * Create a proxy instance from context data and register it as a property in the appropriate
     * namespace (`model`, `querySet`, or `form`).
     * @param {string} name - The unique name of the proxy.
     * @param {Object} contract - Serialized proxy contract from the server.
     * @private
     */
    _registerProxyAsProperty(name, {contract, state}) {
        let proxyClass = PROXY_NAMESPACE_TO_PROXY_CLASS[contract.namespace]

        let proxy;
        if (contract.namespace === 'function') {
            proxy = proxyClass.create({
                http: this.http,
                name: name,
                contract: contract,
            });
        } else {
            proxy = new proxyClass({
                http: this.http,
                name: name,
                contract: contract,
                state: state,
            });
        }

        this[contract.namespace][name] = proxy
    }

    /**
     * Convenience wrapper around {@link GlueHttp.sendRequest}.
     * @param {string} url - The request URL.
     * @param {Object} [requestOptions] - Request configuration options.
     * @returns {Promise<Object>} Response object.
     */
    async fetch(url, requestOptions = {
        body: '',
        method: 'GET',
        contentType: 'application/json',
        csrfProtected: true,
        timeout: null,
    }) {
        return await this.http.sendRequest(url, requestOptions)
    }

    /**
     * Initialize the Glue client with server-provided proxy registry and proxy definitions.
     * @param {Object} proxies - The registered proxies sent from Django page contexxt.
     * @param {GlueConfig} [config] - The GlueConfig instance.
     */
    init({proxies, config = {}}) {
        this._config = config
        this.http = new GlueHttp(this._config)

        for (const [name, proxy] of Object.entries(proxies)) {
            this._registerProxyAsProperty(name, proxy)
        }
    }

    /**
     * Create a new {@link GlueView} instance for server-side HTML rendering.
     * @param {string} url - The target view URL path.
     * @param {Object} [shared_payload] - Payload merged into every request from this view.
     * @returns {GlueView} A new GlueView instance.
     */
    view(url, shared_payload = {}) {
        return new GlueView(this.http, url, shared_payload)
    }
}

export default GlueClient
