import {sendJsonGetRequest, sendKeepLiveRequest} from "./http";
import {SUBJECT_TYPE_TO_PROXY_CLASS} from "./proxies";
import {setConfig} from "./config";
import {SESSION_DATA_URL_PATH} from "./constants";

// TODO: This is becoming a god class and needs to be broken down
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
        }, this.#config.keepLiveIntervalSeconds * 1000)
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
}

export default GlueClient