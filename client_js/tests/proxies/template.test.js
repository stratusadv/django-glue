import {describe, expect, it} from 'bun:test';
import GlueTemplateProxy from '../../src/proxies/template';
import {createMockHttp, createTemplatePolicy} from '../testUtils';

describe('GlueTemplateProxy', () => {
    function makeTemplate(html = '<strong>Hello</strong>') {
        return new GlueTemplateProxy({
            http: createMockHttp({
                result: {html},
                state: null,
            }),
            name: 'card',
            policy: createTemplatePolicy(),
            sharedPayload: {shared: true},
        });
    }

    it('renders html with shared and per-call context', async () => {
        const proxy = makeTemplate();

        const html = await proxy._renderHtml({name: 'Ada'});

        expect(html).toBe('<strong>Hello</strong>');
        expect(proxy.http.sendAttributeEventRequest.mock.calls[0][0].eventKwargs).toEqual({
            shared: true,
            name: 'Ada',
        });
    });

    it('uses the render_html method defined by _defineAttributeProperties', async () => {
        const policy = createTemplatePolicy();
        const proxy = makeTemplate();

        // The policy should have the full attribute path registered
        expect(policy.bound_attributes['GlueTemplateProxy.render_html']).toBeDefined();

        await proxy._renderHtml({});

        // Verify the full attribute path is sent to the server
        const call = proxy.http.sendAttributeEventRequest.mock.calls[0][0];
        expect(call.attribute).toBe('GlueTemplateProxy.render_html');
        expect(call.attribute).not.toBe('render_html');
    });

    it('replaces inner and outer html', async () => {
        const proxy = makeTemplate('<span>Rendered</span>');
        const inner = document.createElement('div');
        const outer = document.createElement('section');
        document.body.appendChild(outer);

        await proxy.renderInnerHtml(inner);
        await proxy.renderOuterHtml(outer);

        expect(inner.innerHTML).toBe('<span>Rendered</span>');
        expect(document.body.lastChild.outerHTML).toBe('<span>Rendered</span>');
    });

    it('inserts adjacent html at requested positions', async () => {
        const proxy = makeTemplate('<em>Rendered</em>');
        const target = document.createElement('div');
        target.innerHTML = '<p>Existing</p>';
        document.body.appendChild(target);

        await proxy.renderInsertAdjacentHtmlBeforeEnd(target);
        await proxy.renderInsertAdjacentHtmlAfterBegin(target);

        expect(target.innerHTML).toBe('<em>Rendered</em><p>Existing</p><em>Rendered</em>');
    });

    it('inserts adjacent html before and after the target element', async () => {
        const proxy = makeTemplate('<em>Rendered</em>');
        const target = document.createElement('div');
        target.textContent = 'Target';
        document.body.appendChild(target);

        await proxy.renderInsertAdjacentHtmlBeforeBegin(target);
        await proxy.renderInsertAdjacentHtmlAfterEnd(target);

        expect(target.previousSibling.outerHTML).toBe('<em>Rendered</em>');
        expect(target.nextSibling.outerHTML).toBe('<em>Rendered</em>');
    });
});
