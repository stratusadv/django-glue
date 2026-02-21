/**
 * Global configuration for Django Glue client.
 */

const DEFAULT_CONFIG = {
    requestTimeoutMs: 30000,
};

let config = { ...DEFAULT_CONFIG };

export function getConfig() {
    return config;
}

export function setConfig(newConfig) {
    config = { ...config, ...newConfig };
}

export function resetConfig() {
    config = { ...DEFAULT_CONFIG };
}