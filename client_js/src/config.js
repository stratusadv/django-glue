/**
 * Global configuration for Django Glue client.
 */

const DEFAULT_CONFIG = {
    requestTimeoutMs: 30000,
    sessionExpiryMessage: 'Django Glue Session expired. Do you want to reload the page?',
    keepLiveIntervalSeconds: 120
};

let config = { ...DEFAULT_CONFIG };

export function getConfig() {
    return config;
}

export function setConfig(newConfig = {}) {
    config = { ...config, ...newConfig };
    return config
}

export function resetConfig() {
    config = { ...DEFAULT_CONFIG };
}