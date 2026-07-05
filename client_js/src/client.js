import GlueHttp from "./http";
import {SUBJECT_TYPE_TO_PROXY_CLASS} from "./proxies";
import GlueView from "./view";

/**
 * Main Django Glue client. Manages proxy initialization, keep-alive polling,
 * and provides the public API for model, queryset, and form proxies.
 */
class GlueClient {
    /** @type {Object} */
    static proxyContracts = {}
    /** @type {Object} */
    static proxyClassesForSubjectTypes = {}
    /** @type {Object} */
    static proxyRegistry = {}

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

    /** @type {number|null} */
    _keepLiveIntervalHandle = null

    /**
     * Create a proxy instance from context data and attach it to the appropriate
     * namespace (`model`, `querySet`, or `form`).
     * @param {string} proxyUniqueName - The unique name of the proxy.
     * @param {Object} proxyContract - Serialized proxy contract from the server.
     * @private
     */
    _defineProxyUniqueNameAsPropertyFromContract(proxyUniqueName, proxyContract) {
        const {subject_type: subjectType} = proxyContract

        let proxyClass = SUBJECT_TYPE_TO_PROXY_CLASS[subjectType]

        if (!(proxyClass.name in this)) {
            this[proxyClass.name] = {}
        }

        let proxy;
        if (subjectType === 'Function') {
            proxy = proxyClass.create({
                http: this.http,
                proxyUniqueName: proxyUniqueName,
                proxyContract: proxyContract,
            });
        } else {
            proxy = new proxyClass({
                http: this.http,
                proxyUniqueName: proxyUniqueName,
                proxyContract: proxyContract,
            });
        }

        this[proxyClass.name][proxyUniqueName] = proxy
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
     * Start (or restart) the keep-alive polling interval. Sends registered proxy
     * names to the server periodically to prevent session expiration.
     * @private
     */
    _initializeKeepLivePulse() {
        if (this._keepLiveIntervalHandle) {
            clearInterval(this._keepLiveIntervalHandle)
        }

        const raiseDisconnectAlert = () => {
            clearInterval(this._keepLiveIntervalHandle)

            let confirmation = confirm(this._config.sessionExpiryMessage)
            if (confirmation) {
                window.location.reload()
            }
        }

        const correctedKeepLiveIntervalSeconds = Math.max(
            this._config.keepLiveIntervalSeconds,
            this._config.minimumKeepLiveIntervalSeconds
        )

        this._keepLiveIntervalHandle = setInterval(() => {
            const keepLiveNames = Object.keys({
                ...this.model,
                ...this.querySet,
                ...this.form,
                ...this.template,
                ...this.function,
            })

            this.http.sendKeepLiveRequest(keepLiveNames).then(response => {
                if (!response.ok) {
                    raiseDisconnectAlert()
                }
            }).catch(err => {
                console.log(err)
                raiseDisconnectAlert()
            })
        }, correctedKeepLiveIntervalSeconds * 1000)
    }

    /**
     * Initialize the Glue client with server-provided proxy registry and proxy definitions.
     * @param {Object} proxyRegistryFromSession - Proxy registry from the Django session.
     * @param {Object} proxyContracts - Serialized proxy contracts for each proxy.
     * @param {GlueConfig} [config] - The GlueConfig instance.
     */
    init({
        proxyContracts,
        config = {},
    }) {
        this._config = config
        this.http = new GlueHttp(this._config)

        this.initializeProxies(proxyRegistryFromSession, proxyContracts)
    }

    /**
     * Initialize proxy instances from registry and proxy definitions, then start keep-alive polling.
     * @param {Object} proxyRegistryFromSession - Proxy registry from the Django session.
     * @param {Object} proxyContracts - Serialized proxy contracts for each proxy.
     */
    initializeProxies(proxyRegistryFromSession, proxyContracts) {
        for (const [proxyUniqueName, proxyContract] of Object.entries(proxyContracts)) {
            this._defineProxyUniqueNameAsPropertyFromContract(proxyUniqueName, proxyContract)
        }

        Object.assign(GlueClient.proxyRegistry, proxyRegistryFromSession)
        Object.assign(GlueClient.proxyContracts, proxyContracts)

        this._initializeKeepLivePulse()
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
