import { describe, it, expect, beforeEach, mock } from 'bun:test';
import GlueTemplateProxy from '../../src/proxies/template';
import { createMockFetch, setupCookieMock } from '../testUtils';

describe('GlueTemplateProxy', () => {
    let mockHttp;
    let proxy;

    const contract = {
        subject_type: 'Template',
        template_name: 'components/card.html',
        definition_proxy_definition: { defaultName: 'World' },
        actions: {
            render_html: {},
        },
    };

    beforeEach(() => {
        mockHttp = {
            sendActionRequest: mock(async (req) => {
                return {
                    data: {
                        html: `<div>${req.payload?.name || 'Default'}</div>`,
                    },
                };
            }),
        };

        proxy = new GlueTemplateProxy({
            http: mockHttp,
            proxyUniqueName: 'card',
            contract: contract,
        });
    });

    describe('constructor', () => {
        it('stores http instance', () => {
            expect(proxy.http).toBe(mockHttp);
        });

        it('stores unique name', () => {
            expect(proxy._uniqueName).toBe('card');
        });

        it('stores proxy definition', () => {
            expect(proxy._contract).toBe(contract);
        });

        it('defaults sharedPayload to empty object', () => {
            expect(proxy._sharedPayload).toEqual({});
        });

        it('accepts sharedPayload option', () => {
            const p = new GlueTemplateProxy({
                http: mockHttp,
                proxyUniqueName: 'card',
                contract: contract,
                sharedPayload: { sharedKey: 'shared' },
            });

            expect(p._sharedPayload).toEqual({ sharedKey: 'shared' });
        });
    });

    describe('static name', () => {
        it('is template for namespace mapping', () => {
            expect(GlueTemplateProxy.name).toBe('template');
        });
    });

    describe('_renderHtml', () => {
        it('calls render_html action with payload', async () => {
            const html = await proxy._renderHtml({ name: 'John' });

            expect(html).toBe('<div>John</div>');
            expect(mockHttp.sendActionRequest).toHaveBeenCalledWith(
                expect.objectContaining({
                    uniqueName: 'card',
                    action: 'render_html',
                    payload: { name: 'John' },
                })
            );
        });

        it('merges sharedPayload with per-call payload', async () => {
            mockHttp.sendActionRequest = mock(async (req) => {
                return {
                    data: {
                        html: JSON.stringify(req.payload),
                    },
                };
            });

            const p = new GlueTemplateProxy({
                http: mockHttp,
                proxyUniqueName: 'card',
                contract: contract,
                sharedPayload: { shared: 'yes', override: 'shared' },
            });

            const html = await p._renderHtml({ call: 'yes', override: 'call' });

            expect(JSON.parse(html)).toEqual({
                shared: 'yes',
                override: 'call',
                call: 'yes',
            });
        });

        it('returns HTML string from response', async () => {
            const html = await proxy._renderHtml({});
            expect(typeof html).toBe('string');
        });
    });

    describe('renderInnerHtml', () => {
        it('sets innerHTML of target element', async () => {
            const el = document.createElement('div');

            await proxy.renderInnerHtml(el, { name: 'Test' });

            expect(el.innerHTML).toBe('<div>Test</div>');
        });
    });

    describe('renderOuterHtml', () => {
        it('sets outerHTML of target element', async () => {
            const parent = document.createElement('div');
            const el = document.createElement('span');
            parent.appendChild(el);

            await proxy.renderOuterHtml(el, { name: 'Replaced' });

            expect(parent.innerHTML).toBe('<div>Replaced</div>');
        });
    });

    describe('renderInsertAdjacentHtmlBeforeEnd', () => {
        it('inserts HTML at end of children', async () => {
            const el = document.createElement('div');
            el.innerHTML = '<span>existing</span>';

            await proxy.renderInsertAdjacentHtmlBeforeEnd(el, { name: 'Appended' });

            expect(el.innerHTML).toBe('<span>existing</span><div>Appended</div>');
        });
    });

    describe('renderInsertAdjacentHtmlAfterEnd', () => {
        it('inserts HTML after the element', async () => {
            const parent = document.createElement('div');
            const el = document.createElement('span');
            const sibling = document.createElement('div');
            parent.appendChild(el);
            parent.appendChild(sibling);

            await proxy.renderInsertAdjacentHtmlAfterEnd(el, { name: 'Inserted' });

            expect(parent.innerHTML).toBe('<span></span><div>Inserted</div><div></div>');
        });
    });

    describe('renderInsertAdjacentHtmlBeforeBegin', () => {
        it('inserts HTML before the element', async () => {
            const parent = document.createElement('div');
            const el = document.createElement('span');
            const sibling = document.createElement('div');
            parent.appendChild(el);
            parent.appendChild(sibling);

            await proxy.renderInsertAdjacentHtmlBeforeBegin(el, { name: 'Inserted' });

            expect(parent.innerHTML).toBe('<div>Inserted</div><span></span><div></div>');
        });
    });

    describe('renderInsertAdjacentHtmlAfterBegin', () => {
        it('inserts HTML at beginning of children', async () => {
            const el = document.createElement('div');
            el.innerHTML = '<span>existing</span>';

            await proxy.renderInsertAdjacentHtmlAfterBegin(el, { name: 'Prepended' });

            expect(el.innerHTML).toBe('<div>Prepended</div><span>existing</span>');
        });
    });

    describe('listener events', () => {
        it('fires before listeners before render', async () => {
            const events = [];

            mockHttp.sendActionRequest = mock(async () => {
                events.push('request');
                return { data: { html: '<div>ok</div>' } };
            });

            proxy.addListener('render_html', () => {
                events.push('before');
            }, 'before');

            await proxy._renderHtml({ name: 'Test' });

            expect(events).toEqual(['before', 'request']);
        });

        it('fires after listeners with result', async () => {
            let capturedEvent = null;

            proxy.addListener('render_html', (event) => {
                capturedEvent = event;
            }, 'after');

            await proxy._renderHtml({ name: 'Test' });

            expect(capturedEvent.result).toEqual({ html: '<div>Test</div>' });
            expect(capturedEvent.action).toBe('render_html');
        });

        it('fires error listeners on failure', async () => {
            let capturedError = null;

            mockHttp.sendActionRequest = mock(async () => {
                throw new Error('server error');
            });

            proxy.addListener('render_html', (event) => {
                capturedError = event.error;
            }, 'error');

            await expect(proxy._renderHtml({})).rejects.toThrow('server error');
            expect(capturedError).toBeInstanceOf(Error);
        });
    });
});
