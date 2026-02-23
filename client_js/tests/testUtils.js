/**
 * Test utilities for mocking fetch, document.cookie, and other browser APIs.
 */

/**
 * Mock fetch implementation that returns configurable responses.
 * @param {Object} responses - Map of URL to response objects
 * @returns {jest.Mock} Mock fetch function
 */
export function createMockFetch(responses = {}) {
    return jest.fn((url, options) => {
        const response = responses[url] || { ok: true, data: {} };
        return Promise.resolve({
            ok: response.ok ?? true,
            text: () => Promise.resolve(JSON.stringify(response.data)),
            json: () => Promise.resolve(response.data),
            clone: function() { return this; }
        });
    });
}

/**
 * Set up document.cookie mock.
 * @param {Object} cookies - Map of cookie names to values
 */
export function setupCookieMock(cookies = {}) {
    const cookieString = Object.entries(cookies)
        .map(([k, v]) => `${k}=${encodeURIComponent(v)}`)
        .join('; ');

    Object.defineProperty(document, 'cookie', {
        value: cookieString,
        writable: true,
        configurable: true
    });
}

/**
 * Create mock context data for proxy tests.
 * @param {Object} fields - Field definitions
 * @param {Object} actions - Action definitions
 * @param {Object} initial - Initial values (for form proxies)
 * @returns {Object} Mock context data
 */
export function createMockContextData(fields = {}, actions = {}, initial = {}) {
    return {
        fields: fields,
        actions: actions,
        initial: initial
    };
}