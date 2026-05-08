import {sendKeepLiveRequest} from "./http";
import {SUBJECT_TYPE_TO_PROXY_CLASS} from "./proxies";
import {setConfig} from "./config";
import {GlueView} from "./view";
import {MINIMUM_KEEP_LIVE_INTERVAL_SECONDS} from "./constants";

class GlueClient {
    static proxyClassesForSubjectTypes = {}
    static contextData = {}
    static proxyRegistry = {}

    #keepLiveIntervalHandle = null
    #config = {}
    $activeProxies = {}

    #defineProxyUniqueNameAsPropertyFromContextData(proxyUniqueName, contextData) {
        const { subject_type: subjectType } = contextData
        this.$activeProxies[proxyUniqueName] = new SUBJECT_TYPE_TO_PROXY_CLASS[subjectType]({
            proxyUniqueName: proxyUniqueName,
            contextData: contextData,
        })

        Object.defineProperty(this, proxyUniqueName, {
            get: () => this.$activeProxies[proxyUniqueName]
        })
    }

    #initializeKeepLivePulse() {
        if (this.#keepLiveIntervalHandle) {
            clearInterval(this.#keepLiveIntervalHandle)
        }

        const raiseDisconnectAlert = () => {
            clearInterval(this.#keepLiveIntervalHandle)

            let confirmation = confirm(this.#config.sessionExpiryMessage)
            if (confirmation) {
                window.location.reload()
            }
        }

        const correctedKeepLiveIntervalSeconds = Math.max(
            this.#config.keepLiveIntervalSeconds,
            MINIMUM_KEEP_LIVE_INTERVAL_SECONDS
        )

        this.#keepLiveIntervalHandle = setInterval(() => {
            const keepLiveNames = Object.keys(this.$activeProxies)
            sendKeepLiveRequest(keepLiveNames).then(response => {
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
        this.#config = setConfig(config)

        this.initializeProxies(proxyRegistryFromSession, contextDataForProxies)
    }

    initializeProxies(proxyRegistryFromSession, contextDataForProxies) {
        for (const [proxyUniqueName, contextData] of Object.entries(contextDataForProxies)) {
            this.#defineProxyUniqueNameAsPropertyFromContextData(proxyUniqueName, contextData)
        }

        Object.assign(GlueClient.proxyRegistry, proxyRegistryFromSession)
        Object.assign(GlueClient.contextData, contextDataForProxies)

        this.#initializeKeepLivePulse()
    }

    view(url, shared_payload = {}) {
        return new GlueView(url, shared_payload)
    }
}

export default GlueClient