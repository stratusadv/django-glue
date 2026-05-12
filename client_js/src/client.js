import GlueHttp from "./http";
import {SUBJECT_TYPE_TO_PROXY_CLASS} from "./proxies";
import GlueView from "./view";

class GlueClient {
    static contextData = {}
    static proxyClassesForSubjectTypes = {}
    static proxyRegistry = {}

    _keepLiveIntervalHandle = null
    _activeProxies = {}

    _defineProxyUniqueNameAsPropertyFromContextData(proxyUniqueName, contextData) {
        const {subject_type: subjectType} = contextData
        this._activeProxies[proxyUniqueName] = new SUBJECT_TYPE_TO_PROXY_CLASS[subjectType]({
            http: this.http,
            proxyUniqueName: proxyUniqueName,
            contextData: contextData,
        })

        Object.defineProperty(this, proxyUniqueName, {
            get: () => this._activeProxies[proxyUniqueName]
        })
    }

    async fetch(url, requestOptions = {
        body: '',
        method: 'GET',
        contentType: 'application/json',
        csrfProtected: true,
        timeout: null,
    }) {
        return await this.http.sendRequest(url, requestOptions)
    }

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
            const keepLiveNames = Object.keys(this._activeProxies)
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

    init({
             proxyRegistryFromSession,
             contextDataForProxies,
             config = {},
         }) {
        this._config = config
        this.http = new GlueHttp(this._config)

        this.initializeProxies(proxyRegistryFromSession, contextDataForProxies)
    }

    initializeProxies(proxyRegistryFromSession, contextDataForProxies) {
        for (const [proxyUniqueName, contextData] of Object.entries(contextDataForProxies)) {
            this._defineProxyUniqueNameAsPropertyFromContextData(proxyUniqueName, contextData)
        }

        Object.assign(GlueClient.proxyRegistry, proxyRegistryFromSession)
        Object.assign(GlueClient.contextData, contextDataForProxies)

        this._initializeKeepLivePulse()
    }

    view(url, shared_payload = {}) {
        return new GlueView(this.http, url, shared_payload)
    }
}

export default GlueClient