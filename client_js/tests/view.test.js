import { describe, it, expect, beforeEach, afterEach, mock } from 'bun:test';
import GlueView from '../src/view';
import { setupCookieMock } from './testUtils';

describe('GlueView', () => {
    let originalLocation;
    let mockHttp;

    const createConfig = () => ({
        requestTimeoutSeconds: 30,
        actionUrlPath: '/__dg__/action/',
        keepLiveUrlPath: '/__dg__/keep_live/',
        glueViewUrlPath: '/__dg__/glue_view/',
    });

    beforeEach(() => {
        originalLocation = window.location;
        Object.defineProperty(window, 'location', {
            value: { origin: 'http://localhost:3000', pathname: '/current/page' },
            writable: true,
            configurable: true,
        });

        setupCookieMock({ csrftoken: 'test-token' });

        window.Glue = {
            initializeProxies: mock(() => {}),
        };

        const sendRequestMock = mock(() => Promise.resolve({
            data: {
                html: '<div>Rendered HTML</div>',
                proxy_registry_data: {},
                proxy_definitions: {},
            },
        }));

        mockHttp = {
            _config: createConfig(),
            sendRequest: sendRequestMock,
        };
    });

    afterEach(() => {
        Object.defineProperty(window, 'location', {
            value: originalLocation,
            writable: true,
            configurable: true,
        });
    });

    describe('constructor', () => {
        it('sets url from provided path', () => {
            const view = new GlueView(mockHttp, '/some/url/');
            expect(view.url).toBe('/some/url/');
        });

        it('sets shared_payload', () => {
            const view = new GlueView(mockHttp, '/url/', { key: 'value' });
            expect(view.shared_payload).toEqual({ key: 'value' });
        });

        it('appends glue_encode_path when skipEncodePath is false', () => {
            const view = new GlueView(mockHttp, '/some/url/', {}, false);
            expect(view.url).toContain('glue_encode_path');
        });

        it('does not append glue_encode_path when skipEncodePath is true', () => {
            const view = new GlueView(mockHttp, '/some/url/', {}, true);
            expect(view.url).toBe('/some/url/');
        });

        it('preserves query params from url', () => {
            const view = new GlueView(mockHttp, '/some/url/?foo=bar');
            expect(view.url).toBe('/some/url/?foo=bar');
        });
    });

    describe('get', () => {
        it('sends GET method to server', async () => {
            const view = new GlueView(mockHttp, '/test/');
            const result = await view.get({ param: 'value' });

            expect(result).toBe('<div>Rendered HTML</div>');

            const call = mockHttp.sendRequest.mock.calls[0];
            const body = JSON.parse(call[1].body);
            expect(body.method).toBe('GET');
            expect(body.view_payload.param).toBe('value');
        });

        it('merges shared_payload with request payload', async () => {
            const view = new GlueView(mockHttp, '/test/', { shared: 'data' });
            await view.get({ extra: 'param' });

            const call = mockHttp.sendRequest.mock.calls[0];
            const body = JSON.parse(call[1].body);
            expect(body.view_payload.shared).toBe('data');
            expect(body.view_payload.extra).toBe('param');
        });
    });

    describe('post', () => {
        it('sends POST method to server', async () => {
            const view = new GlueView(mockHttp, '/test/');
            await view.post({ param: 'value' });

            const call = mockHttp.sendRequest.mock.calls[0];
            const body = JSON.parse(call[1].body);
            expect(body.method).toBe('POST');
        });
    });

    describe('_fetchView', () => {
        it('calls initializeProxies on response', async () => {
            const initSpy = mock(() => {});
            window.Glue = { initializeProxies: initSpy };

            const view = new GlueView(mockHttp, '/test/');
            await view._fetchView();

            expect(initSpy).toHaveBeenCalledWith({}, {});
        });

        it('returns html from response', async () => {
            const view = new GlueView(mockHttp, '/test/');
            const result = await view._fetchView();
            expect(result).toBe('<div>Rendered HTML</div>');
        });

        it('sends csrfProtected true', async () => {
            const view = new GlueView(mockHttp, '/test/');
            await view._fetchView();

            const call = mockHttp.sendRequest.mock.calls[0];
            expect(call[1].csrfProtected).toBe(true);
        });
    });

    describe('renderInnerHtml', () => {
        it('sets innerHTML of target element', async () => {
            const view = new GlueView(mockHttp, '/test/');
            const el = document.createElement('div');
            document.body.appendChild(el);

            await view.renderInnerHtml(el);

            expect(el.innerHTML).toBe('<div>Rendered HTML</div>');
        });
    });

    describe('renderOuterHtml', () => {
        it('replaces element with rendered HTML', async () => {
            const view = new GlueView(mockHttp, '/test/');
            const el = document.createElement('span');
            el.id = 'target';
            document.body.appendChild(el);

            await view.renderOuterHtml(el);

            expect(document.getElementById('target')).toBeNull();
            expect(document.body.lastChild.outerHTML).toBe('<div>Rendered HTML</div>');
        });
    });

    describe('renderInsertAdjacentHtmlBeforeEnd', () => {
        it('inserts HTML before end of target', async () => {
            const view = new GlueView(mockHttp, '/test/');
            const el = document.createElement('div');
            el.innerHTML = '<p>Existing</p>';
            document.body.appendChild(el);

            await view.renderInsertAdjacentHtmlBeforeEnd(el);

            expect(el.innerHTML).toBe('<p>Existing</p><div>Rendered HTML</div>');
        });
    });

    describe('renderInsertAdjacentHtmlAfterEnd', () => {
        it('inserts HTML after end of target', async () => {
            const view = new GlueView(mockHttp, '/test/');
            const el = document.createElement('div');
            el.innerHTML = '<p>Existing</p>';
            document.body.appendChild(el);

            await view.renderInsertAdjacentHtmlAfterEnd(el);

            expect(el.nextSibling.outerHTML).toBe('<div>Rendered HTML</div>');
        });
    });

    describe('renderInsertAdjacentHtmlBeforeBegin', () => {
        it('inserts HTML before begin of target', async () => {
            const view = new GlueView(mockHttp, '/test/');
            const el = document.createElement('div');
            el.innerHTML = '<p>Existing</p>';
            document.body.appendChild(el);

            await view.renderInsertAdjacentHtmlBeforeBegin(el);

            expect(el.previousSibling.outerHTML).toBe('<div>Rendered HTML</div>');
        });
    });

    describe('renderInsertAdjacentHtmlAfterBegin', () => {
        it('inserts HTML after begin of target', async () => {
            const view = new GlueView(mockHttp, '/test/');
            const el = document.createElement('div');
            el.innerHTML = '<p>Existing</p>';
            document.body.appendChild(el);

            await view.renderInsertAdjacentHtmlAfterBegin(el);

            expect(el.innerHTML).toBe('<div>Rendered HTML</div><p>Existing</p>');
        });
    });
});
