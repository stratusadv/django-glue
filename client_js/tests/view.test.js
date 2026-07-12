import {afterEach, beforeEach, describe, expect, it, mock} from 'bun:test';
import GlueView from '../src/view';

describe('GlueView', () => {
    let originalLocation;
    let mockHttp;
    let glueInit;

    beforeEach(() => {
        originalLocation = window.location;
        Object.defineProperty(window, 'location', {
            value: {origin: 'http://localhost:3000', pathname: '/current/page'},
            writable: true,
            configurable: true,
        });

        glueInit = mock(() => {});
        window.Glue = {init: glueInit};

        mockHttp = {
            _config: {
                glueViewUrlPath: '/__dg__/glue_view/',
                attributeEventUrlPath: '/__dg__/bound_attribute_event/',
            },
            sendRequest: mock(async () => ({
                data: {
                    html: '<div>Rendered HTML</div>',
                    proxies: {contact: {policy: {}, state: {}}},
                },
            })),
        };
    });

    afterEach(() => {
        Object.defineProperty(window, 'location', {
            value: originalLocation,
            writable: true,
            configurable: true,
        });
    });

    it('preserves URL path and can append glue_encode_path', () => {
        expect(new GlueView(mockHttp, '/some/url/').url).toBe('/some/url/');
        expect(new GlueView(mockHttp, '/some/url/?q=1').url).toBe('/some/url/?q=1');
        expect(new GlueView(mockHttp, '/some/url/', {}, false).url).toContain('glue_encode_path');
    });

    it('posts view requests through the configured glue view URL', async () => {
        const view = new GlueView(mockHttp, '/fragment/', {shared: true});
        const html = await view.get({page: 2});

        const [url, options] = mockHttp.sendRequest.mock.calls[0];
        const body = JSON.parse(options.body);

        expect(html).toBe('<div>Rendered HTML</div>');
        expect(url).toBe('/__dg__/glue_view/');
        expect(body).toEqual({
            url_path: '/fragment/',
            method: 'GET',
            view_payload: {shared: true, page: 2},
        });
        expect(options.csrfProtected).toBe(true);
    });

    it('initializes returned proxies on the global Glue client', async () => {
        const view = new GlueView(mockHttp, '/fragment/');
        await view.post();

        expect(glueInit).toHaveBeenCalledWith({
            proxies: {contact: {policy: {}, state: {}}},
            config: mockHttp._config,
        });
    });

    it('renders html into target elements', async () => {
        const view = new GlueView(mockHttp, '/fragment/');
        const inner = document.createElement('div');
        const outer = document.createElement('span');
        document.body.appendChild(outer);

        await view.renderInnerHtml(inner);
        await view.renderOuterHtml(outer);

        expect(inner.innerHTML).toBe('<div>Rendered HTML</div>');
        expect(document.body.lastChild.outerHTML).toBe('<div>Rendered HTML</div>');
    });

    it('inserts adjacent html', async () => {
        const view = new GlueView(mockHttp, '/fragment/');
        const target = document.createElement('div');
        target.innerHTML = '<p>Existing</p>';
        document.body.appendChild(target);

        await view.renderInsertAdjacentHtmlBeforeEnd(target);
        await view.renderInsertAdjacentHtmlAfterBegin(target);

        expect(target.innerHTML).toBe('<div>Rendered HTML</div><p>Existing</p><div>Rendered HTML</div>');
    });

    it('inserts adjacent html before and after target elements', async () => {
        const view = new GlueView(mockHttp, '/fragment/');
        const target = document.createElement('div');
        target.textContent = 'Target';
        document.body.appendChild(target);

        await view.renderInsertAdjacentHtmlBeforeBegin(target);
        await view.renderInsertAdjacentHtmlAfterEnd(target);

        expect(target.previousSibling.outerHTML).toBe('<div>Rendered HTML</div>');
        expect(target.nextSibling.outerHTML).toBe('<div>Rendered HTML</div>');
    });
});
