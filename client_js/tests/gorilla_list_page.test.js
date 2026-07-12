import {afterEach, beforeEach, describe, expect, it} from 'bun:test';

describe('Gorilla list page query controls', () => {
    let container;

    const fighters = [
        {id: 1, name: 'Gorilla Grit', age: 26, rank_points: 4657},
        {id: 2, name: 'Banana Basher', age: 55, rank_points: 1200},
        {id: 3, name: 'Brutus the Beast', age: 31, rank_points: 4322},
        {id: 4, name: 'Iron Jaw Joe', age: 44, rank_points: 3000},
    ];

    beforeEach(() => {
        container = document.createElement('div');
        document.body.appendChild(container);
    });

    afterEach(() => {
        container.remove();
    });

    function createQuerySet(items) {
        return {
            calls: [],
            async queryWithParams(params) {
                this.calls.push(JSON.parse(JSON.stringify(params)));

                let result = [...items];
                const search = params.filter?.name__icontains?.toLowerCase();
                if (search) {
                    result = result.filter(item => item.name.toLowerCase().includes(search));
                }

                const orderBy = params.order_by;
                if (orderBy) {
                    const descending = orderBy.startsWith('-');
                    const fieldName = descending ? orderBy.slice(1) : orderBy;
                    result.sort((left, right) => {
                        if (left[fieldName] < right[fieldName]) return descending ? 1 : -1;
                        if (left[fieldName] > right[fieldName]) return descending ? -1 : 1;
                        return 0;
                    });
                }

                const start = params.slice?.start ?? 0;
                const stop = params.slice?.stop ?? result.length;
                return result.slice(start, stop);
            },
        };
    }

    function createListPageHarness({querySet = createQuerySet(fighters)} = {}) {
        const state = {
            search: '',
            sliceStart: 0,
            sliceStop: 100,
            orderBy: 'name',
            get queryParams() {
                return {
                    filter: {name__icontains: this.search},
                    slice: {start: this.sliceStart, stop: this.sliceStop},
                    order_by: this.orderBy,
                };
            },
        };

        container.innerHTML = `
            <input data-control="slice-start" type="number" value="${state.sliceStart}">
            <input data-control="slice-stop" type="number" value="${state.sliceStop}">
            <select data-control="order-by">
                <option value="name">Name (A-Z)</option>
                <option value="-name">Name (Z-A)</option>
                <option value="age">Age (Low to High)</option>
                <option value="-age">Age (High to Low)</option>
                <option value="rank_points">Rank Points (Low to High)</option>
                <option value="-rank_points">Rank Points (High to Low)</option>
            </select>
            <input data-control="search" type="text" value="${state.search}">
            <div data-list="fighters"></div>
        `;

        const list = container.querySelector('[data-list="fighters"]');
        const render = async () => {
            const items = await querySet.queryWithParams(state.queryParams);
            list.innerHTML = items
                .map(item => `<article data-card="${item.id}">${item.name}</article>`)
                .join('');
        };

        container.querySelector('[data-control="search"]').addEventListener('input', async event => {
            state.search = event.target.value;
            await render();
        });
        container.querySelector('[data-control="slice-start"]').addEventListener('input', async event => {
            state.sliceStart = Number(event.target.value);
            await render();
        });
        container.querySelector('[data-control="slice-stop"]').addEventListener('input', async event => {
            state.sliceStop = Number(event.target.value);
            await render();
        });
        container.querySelector('[data-control="order-by"]').addEventListener('change', async event => {
            state.orderBy = event.target.value;
            await render();
        });

        return {querySet, render, state};
    }

    function visibleNames() {
        return [...container.querySelectorAll('[data-card]')].map(card => card.textContent);
    }

    async function setInput(selector, value) {
        const input = container.querySelector(selector);
        input.value = value;
        input.dispatchEvent(new Event('input', {bubbles: true}));
        await Promise.resolve();
    }

    async function selectOption(selector, value) {
        const select = container.querySelector(selector);
        select.value = value;
        select.dispatchEvent(new Event('change', {bubbles: true}));
        await Promise.resolve();
    }

    it('queries with the list page default search, slice, and ordering params', async () => {
        const {querySet, render} = createListPageHarness();

        await render();

        expect(querySet.calls.at(-1)).toEqual({
            filter: {name__icontains: ''},
            slice: {start: 0, stop: 100},
            order_by: 'name',
        });
        expect(visibleNames()).toEqual([
            'Banana Basher',
            'Brutus the Beast',
            'Gorilla Grit',
            'Iron Jaw Joe',
        ]);
    });

    it('updates query params and visible cards when search text changes', async () => {
        const {querySet, render} = createListPageHarness();
        await render();

        await setInput('[data-control="search"]', 'brut');

        expect(querySet.calls.at(-1)).toEqual({
            filter: {name__icontains: 'brut'},
            slice: {start: 0, stop: 100},
            order_by: 'name',
        });
        expect(visibleNames()).toEqual(['Brutus the Beast']);
    });

    it('updates query params and visible card order when ordering changes', async () => {
        const {querySet, render} = createListPageHarness();
        await render();

        await selectOption('[data-control="order-by"]', '-age');

        expect(querySet.calls.at(-1)).toEqual({
            filter: {name__icontains: ''},
            slice: {start: 0, stop: 100},
            order_by: '-age',
        });
        expect(visibleNames()).toEqual([
            'Banana Basher',
            'Iron Jaw Joe',
            'Brutus the Beast',
            'Gorilla Grit',
        ]);
    });

    it('updates query params and visible cards when slice bounds change', async () => {
        const {querySet, render} = createListPageHarness();
        await render();

        await setInput('[data-control="slice-start"]', '1');
        await setInput('[data-control="slice-stop"]', '3');

        expect(querySet.calls.at(-1)).toEqual({
            filter: {name__icontains: ''},
            slice: {start: 1, stop: 3},
            order_by: 'name',
        });
        expect(visibleNames()).toEqual(['Brutus the Beast', 'Gorilla Grit']);
    });

    it('combines search, ordering, and slicing in the same queryset request', async () => {
        const {querySet, render} = createListPageHarness();
        await render();

        await setInput('[data-control="search"]', 'i');
        await selectOption('[data-control="order-by"]', '-rank_points');
        await setInput('[data-control="slice-start"]', '0');
        await setInput('[data-control="slice-stop"]', '2');

        expect(querySet.calls.at(-1)).toEqual({
            filter: {name__icontains: 'i'},
            slice: {start: 0, stop: 2},
            order_by: '-rank_points',
        });
        expect(visibleNames()).toEqual(['Gorilla Grit', 'Iron Jaw Joe']);
    });
});
