import {describe, expect, it, beforeEach, afterEach, mock} from 'bun:test';
import GlueModelProxy from '../../src/proxies/model';
import GlueFormProxy from '../../src/proxies/form';
import {createMockHttp, createModelPolicy, createFormPolicy, createState} from '../testUtils';

/**
 * These tests verify that proxy state updates correctly propagate to rendered HTML.
 *
 * This simulates how reactive frameworks (like Alpine.js) bind to proxy properties:
 * 1. They wrap the proxy's _state object in their own reactive proxy
 * 2. They read values through getters and render to DOM
 * 3. When values change, they re-render
 *
 * The key behavior being tested: when _handleEventResponse updates instance_data,
 * it must mutate the SAME object (not replace it) so that reactive framework
 * proxies continue to track changes.
 */
describe('Proxy Reactivity with DOM Rendering', () => {
    let container;

    beforeEach(() => {
        container = document.createElement('div');
        container.id = 'test-container';
        document.body.appendChild(container);
    });

    afterEach(() => {
        container.remove();
    });

    /**
     * Simulates a reactive framework's binding behavior.
     * Wraps the state object and re-renders when properties are set.
     */
    function createReactiveBinding(proxy, renderFn) {
        const originalInstanceData = proxy._state.instance_data;

        // Wrap instance_data in a Proxy to detect property changes (like Alpine does)
        const reactiveInstanceData = new Proxy(originalInstanceData, {
            set(target, property, value) {
                target[property] = value;
                // Re-render when any property changes
                renderFn();
                return true;
            },
            deleteProperty(target, property) {
                delete target[property];
                renderFn();
                return true;
            }
        });

        // Replace instance_data with our reactive proxy
        proxy._state.instance_data = reactiveInstanceData;

        // Initial render
        renderFn();

        return {
            originalInstanceData,
            reactiveInstanceData,
        };
    }

    function makeModel(instanceData = {id: 1, name: 'Koko', age: 25}) {
        const state = createState(instanceData);
        return new GlueModelProxy({
            http: createMockHttp({result: {}, state}),
            name: 'gorilla',
            policy: createModelPolicy(),
            state,
        });
    }

    it('updates rendered HTML when instance_data values change via _handleEventResponse', () => {
        const proxy = makeModel({id: 1, name: 'Koko', age: 25});

        // Simulate reactive framework binding
        const renderFn = () => {
            container.innerHTML = `
                <span data-field="name">${proxy._state.instance_data.name}</span>
                <span data-field="age">${proxy._state.instance_data.age}</span>
            `;
        };
        createReactiveBinding(proxy, renderFn);

        // Verify initial render
        expect(container.querySelector('[data-field="name"]').textContent).toBe('Koko');
        expect(container.querySelector('[data-field="age"]').textContent).toBe('25');

        // Simulate server response updating values
        proxy._handleEventResponse('save', {}, {
            state: {
                namespace: 'model',
                instance_data: {id: 1, name: 'Kong', age: 30},
                errors: {},
            },
        });

        // HTML should reflect the new values
        expect(container.querySelector('[data-field="name"]').textContent).toBe('Kong');
        expect(container.querySelector('[data-field="age"]').textContent).toBe('30');
    });

    it('updates rendered HTML on multiple consecutive state changes', () => {
        const proxy = makeModel({id: 1, name: 'Koko', age: 25});

        const renderFn = () => {
            container.innerHTML = `<span data-field="age">${proxy._state.instance_data.age}</span>`;
        };
        createReactiveBinding(proxy, renderFn);

        expect(container.querySelector('[data-field="age"]').textContent).toBe('25');

        // First update
        proxy._handleEventResponse('increment', {}, {
            state: {namespace: 'model', instance_data: {id: 1, name: 'Koko', age: 26}, errors: {}},
        });
        expect(container.querySelector('[data-field="age"]').textContent).toBe('26');

        // Second update
        proxy._handleEventResponse('increment', {}, {
            state: {namespace: 'model', instance_data: {id: 1, name: 'Koko', age: 27}, errors: {}},
        });
        expect(container.querySelector('[data-field="age"]').textContent).toBe('27');

        // Third update
        proxy._handleEventResponse('increment', {}, {
            state: {namespace: 'model', instance_data: {id: 1, name: 'Koko', age: 28}, errors: {}},
        });
        expect(container.querySelector('[data-field="age"]').textContent).toBe('28');
    });

    it('maintains reactive binding when new fields are added', () => {
        const proxy = makeModel({id: 1, name: 'Koko'});

        const renderFn = () => {
            const score = proxy._state.instance_data.score ?? 'N/A';
            container.innerHTML = `<span data-field="score">${score}</span>`;
        };
        createReactiveBinding(proxy, renderFn);

        expect(container.querySelector('[data-field="score"]').textContent).toBe('N/A');

        // Server adds a new field
        proxy._handleEventResponse('calculate', {}, {
            state: {namespace: 'model', instance_data: {id: 1, name: 'Koko', score: 95}, errors: {}},
        });

        expect(container.querySelector('[data-field="score"]').textContent).toBe('95');
    });

    it('maintains reactive binding when fields are removed', () => {
        const proxy = makeModel({id: 1, name: 'Koko', tempField: 'temporary'});

        const renderFn = () => {
            const temp = proxy._state.instance_data.tempField ?? 'removed';
            container.innerHTML = `<span data-field="temp">${temp}</span>`;
        };
        createReactiveBinding(proxy, renderFn);

        expect(container.querySelector('[data-field="temp"]').textContent).toBe('temporary');

        // Server response doesn't include tempField
        proxy._handleEventResponse('save', {}, {
            state: {namespace: 'model', instance_data: {id: 1, name: 'Koko'}, errors: {}},
        });

        expect(container.querySelector('[data-field="temp"]').textContent).toBe('removed');
    });

    it('preserves reactive proxy wrapper after state update', () => {
        const proxy = makeModel({id: 1, name: 'Koko', age: 25});

        const {originalInstanceData, reactiveInstanceData} = createReactiveBinding(proxy, () => {
            container.innerHTML = `<span>${proxy._state.instance_data.age}</span>`;
        });

        // The reactive proxy should still be the same object reference
        expect(proxy._state.instance_data).toBe(reactiveInstanceData);

        proxy._handleEventResponse('save', {}, {
            state: {namespace: 'model', instance_data: {id: 1, name: 'Koko', age: 30}, errors: {}},
        });

        // After update, it should STILL be the same reactive proxy
        expect(proxy._state.instance_data).toBe(reactiveInstanceData);
        // And the underlying target should be the original object
        expect(Object.getPrototypeOf(proxy._state.instance_data)).toBe(Object.prototype);
    });

    it('updates HTML when accessing values through field property getters', () => {
        const proxy = makeModel({id: 1, name: 'Koko', age: 25});

        // Render using the proxy's field getter (like x-model="gorilla.age" would)
        const renderFn = () => {
            container.innerHTML = `
                <input data-field="name" value="${proxy.name}" />
                <input data-field="age" value="${proxy.age}" />
            `;
        };
        createReactiveBinding(proxy, renderFn);

        expect(container.querySelector('[data-field="name"]').value).toBe('Koko');
        expect(container.querySelector('[data-field="age"]').value).toBe('25');

        proxy._handleEventResponse('save', {}, {
            state: {namespace: 'model', instance_data: {id: 1, name: 'Kong', age: 30}, errors: {}},
        });

        expect(container.querySelector('[data-field="name"]').value).toBe('Kong');
        expect(container.querySelector('[data-field="age"]').value).toBe('30');
    });

    it('updates HTML when accessing values through $fields.fieldName.value', () => {
        const proxy = makeModel({id: 1, name: 'Koko', age: 25});

        // Render using $fields accessor (like x-model="gorilla.$fields.age.value" would)
        const renderFn = () => {
            container.innerHTML = `
                <input data-field="name" value="${proxy.$fields.name.value}" />
                <input data-field="age" value="${proxy.$fields.age.value}" />
            `;
        };
        createReactiveBinding(proxy, renderFn);

        expect(container.querySelector('[data-field="name"]').value).toBe('Koko');
        expect(container.querySelector('[data-field="age"]').value).toBe('25');

        proxy._handleEventResponse('save', {}, {
            state: {namespace: 'model', instance_data: {id: 1, name: 'Kong', age: 30}, errors: {}},
        });

        expect(container.querySelector('[data-field="name"]').value).toBe('Kong');
        expect(container.querySelector('[data-field="age"]').value).toBe('30');
    });

    it('updates field validation DOM after save responses', () => {
        const state = createState({age: 71});
        const policy = createFormPolicy({
            subject_details: {
                included_fields: {
                    age: {type: 'IntegerField', label: 'Age'},
                },
            },
        });
        const proxy = new GlueFormProxy({
            http: createMockHttp({result: null, state}),
            name: 'gorilla',
            policy,
            state,
        });

        const renderFn = () => {
            const field = proxy.$fields.age;
            container.innerHTML = `
                <input
                    data-field="age"
                    class="${field.hasErrors ? 'is-invalid' : ''}"
                    value="${field.value}">
                <div data-feedback="age">${field.errorText || ''}</div>
            `;
        };

        proxy.$fields.age = new Proxy(proxy.$fields.age, {
            set(target, property, value) {
                target[property] = value;
                renderFn();
                return true;
            },
        });
        renderFn();

        expect(container.querySelector('[data-field="age"]').classList.contains('is-invalid')).toBe(false);
        expect(container.querySelector('[data-feedback="age"]').textContent).toBe('');

        proxy._handleEventResponse('GlueFormProxy.save', null, {
            result: null,
            state: {
                namespace: 'form',
                instance_data: {age: 71},
                errors: {age: ['Ensure this value is less than or equal to 60.']},
            },
        });

        expect(container.querySelector('[data-field="age"]').classList.contains('is-invalid')).toBe(true);
        expect(container.querySelector('[data-feedback="age"]').textContent).toBe(
            'Ensure this value is less than or equal to 60.',
        );

        proxy._handleEventResponse('GlueFormProxy.save', null, {
            result: null,
            state: {
                namespace: 'form',
                instance_data: {age: 60},
                errors: {},
            },
        });

        expect(container.querySelector('[data-field="age"]').classList.contains('is-invalid')).toBe(false);
        expect(container.querySelector('[data-feedback="age"]').textContent).toBe('');
    });
});

/**
 * Tests for ModelChoiceField choices loading and HTML rendering.
 * These verify that choices load correctly and render in the DOM.
 */
describe('ModelChoiceField Choices DOM Rendering', () => {
    let container;

    beforeEach(() => {
        GlueFormProxy.choicesCache.clear();
        container = document.createElement('div');
        container.id = 'choices-test-container';
        document.body.appendChild(container);
    });

    afterEach(() => {
        container.remove();
    });

    function makeFormWithChoiceField(choicesResponse = [
        {pk: 1, __str__: 'Option A'},
        {pk: 2, __str__: 'Option B'},
        {pk: 3, __str__: 'Option C'},
    ]) {
        const policy = createFormPolicy({
            subject_details: {
                included_fields: {
                    category: {type: 'ModelChoiceField', label: 'Category'},
                },
            },
        });
        const state = createState({category: null});
        return new GlueFormProxy({
            http: createMockHttp({result: choicesResponse, state}),
            name: 'item',
            policy,
            state,
        });
    }

    function makeFormWithMultipleChoiceField(choicesResponse = [
        {pk: 1, __str__: 'Skill A'},
        {pk: 2, __str__: 'Skill B'},
    ]) {
        const policy = createFormPolicy({
            subject_details: {
                included_fields: {
                    skills: {type: 'ModelMultipleChoiceField', label: 'Skills'},
                },
            },
        });
        const state = createState({skills: []});
        return new GlueFormProxy({
            http: createMockHttp({result: choicesResponse, state}),
            name: 'gorilla',
            policy,
            state,
        });
    }

    it('renders multiple choice checkboxes after lazy foreign_key_choices array response', async () => {
        const proxy = makeFormWithMultipleChoiceField([
            {pk: 1, __str__: 'Chest Pound'},
            {pk: 2, __str__: 'Ground Slam'},
        ]);

        const renderCheckboxes = () => {
            const choices = proxy.$fields.skills.choices || [];
            container.innerHTML = `
                <div class="checkbox-group">
                    ${choices.map(choice => `
                        <label>
                            <input type="checkbox" name="skills" value="${choice.pk}" />
                            ${choice.__str__}
                        </label>
                    `).join('')}
                </div>
            `;
        };

        renderCheckboxes();
        expect(container.querySelectorAll('input[type="checkbox"]').length).toBe(0);

        await new Promise(resolve => setTimeout(resolve, 0));
        renderCheckboxes();

        const checkboxes = container.querySelectorAll('input[type="checkbox"]');
        const labels = Array.from(container.querySelectorAll('label'))
            .map(label => label.textContent.trim());

        expect(proxy.http.sendAttributeEventRequest.mock.calls[0][0].eventKwargs).toEqual({
            field_name: 'skills',
            choice_fields: [],
        });
        expect(checkboxes.length).toBe(2);
        expect(checkboxes[0].value).toBe('1');
        expect(checkboxes[1].value).toBe('2');
        expect(labels).toEqual(['Chest Pound', 'Ground Slam']);
    });

    it('renders empty select when choices have not loaded yet', () => {
        const proxy = makeFormWithChoiceField();

        // Render a select element based on choices (simulating x-for="choice in field.choices")
        const renderChoices = () => {
            const choices = proxy.$fields.category.choices || [];
            container.innerHTML = `
                <select data-field="category">
                    ${choices.map(choice =>
                        `<option value="${choice.pk}">${choice.__str__}</option>`
                    ).join('')}
                </select>
            `;
        };
        renderChoices();

        // Initially no options because choices haven't loaded
        const options = container.querySelectorAll('option');
        expect(options.length).toBe(0);
    });

    it('renders select options after choices are loaded via _handleEventResponse', () => {
        const proxy = makeFormWithChoiceField();

        const renderChoices = () => {
            const choices = proxy.$fields.category.choices || [];
            container.innerHTML = `
                <select data-field="category">
                    ${choices.map(choice =>
                        `<option value="${choice.pk}">${choice.__str__}</option>`
                    ).join('')}
                </select>
            `;
        };

        // Simulate server response with choices
        proxy._handleEventResponse(
            'foreign_key_choices',
            {field_name: 'category'},
            {
                result: [
                    {pk: 1, __str__: 'Tech'},
                    {pk: 2, __str__: 'Sports'},
                    {pk: 3, __str__: 'Music'},
                ],
                state: proxy._state,
            },
        );

        // Re-render after choices loaded
        renderChoices();

        const options = container.querySelectorAll('option');
        expect(options.length).toBe(3);
        expect(options[0].value).toBe('1');
        expect(options[0].textContent).toBe('Tech');
        expect(options[1].value).toBe('2');
        expect(options[1].textContent).toBe('Sports');
        expect(options[2].value).toBe('3');
        expect(options[2].textContent).toBe('Music');
    });

    it('renders checkboxes for multiple choice fields', () => {
        const proxy = makeFormWithChoiceField();

        const renderCheckboxes = () => {
            const choices = proxy.$fields.category.choices || [];
            container.innerHTML = `
                <div class="checkbox-group">
                    ${choices.map(choice => `
                        <label>
                            <input type="checkbox" name="category" value="${choice.pk}" />
                            ${choice.__str__}
                        </label>
                    `).join('')}
                </div>
            `;
        };

        // Simulate server response
        proxy._handleEventResponse(
            'foreign_key_choices',
            {field_name: 'category'},
            {result: [{pk: 1, __str__: 'Skill A'}, {pk: 2, __str__: 'Skill B'}], state: proxy._state},
        );

        renderCheckboxes();

        const checkboxes = container.querySelectorAll('input[type="checkbox"]');
        expect(checkboxes.length).toBe(2);
        expect(checkboxes[0].value).toBe('1');
        expect(checkboxes[1].value).toBe('2');
    });

    it('updates choices array correctly for saving selected values', () => {
        const proxy = makeFormWithChoiceField();
        const state = proxy._state;
        state.instance_data.category = [1]; // Pre-select first option

        // Simulate server response with choices
        proxy._handleEventResponse(
            'foreign_key_choices',
            {field_name: 'category'},
            {
                result: [
                    {pk: 1, __str__: 'Skill A'},
                    {pk: 2, __str__: 'Skill B'},
                    {pk: 3, __str__: 'Skill C'},
                ],
                state,
            },
        );

        const renderCheckboxes = () => {
            const choices = proxy.$fields.category.choices || [];
            const selected = state.instance_data.category || [];
            container.innerHTML = `
                <div class="checkbox-group">
                    ${choices.map(choice => `
                        <label>
                            <input
                                type="checkbox"
                                name="category"
                                value="${choice.pk}"
                                ${selected.includes(choice.pk) ? 'checked' : ''}
                            />
                            ${choice.__str__}
                        </label>
                    `).join('')}
                </div>
            `;
        };

        renderCheckboxes();

        // First checkbox should be checked
        const checkboxes = container.querySelectorAll('input[type="checkbox"]');
        expect(checkboxes[0].checked).toBe(true);
        expect(checkboxes[1].checked).toBe(false);
        expect(checkboxes[2].checked).toBe(false);

        // Simulate user checking another option
        state.instance_data.category = [1, 3];
        renderCheckboxes();

        const updatedCheckboxes = container.querySelectorAll('input[type="checkbox"]');
        expect(updatedCheckboxes[0].checked).toBe(true);
        expect(updatedCheckboxes[1].checked).toBe(false);
        expect(updatedCheckboxes[2].checked).toBe(true);
    });

    it('choices data persists across multiple accesses', () => {
        const proxy = makeFormWithChoiceField();

        // Load choices
        proxy._handleEventResponse(
            'foreign_key_choices',
            {field_name: 'category'},
            {result: [{pk: 1, __str__: 'A'}, {pk: 2, __str__: 'B'}], state: proxy._state},
        );

        // Access choices multiple times
        const choices1 = proxy.$fields.category.choices;
        const choices2 = proxy.$fields.category.choices;
        const choices3 = proxy.$fields.category.choices;

        // All should return the same data
        expect(choices1).toEqual([{pk: 1, __str__: 'A'}, {pk: 2, __str__: 'B'}]);
        expect(choices2).toEqual([{pk: 1, __str__: 'A'}, {pk: 2, __str__: 'B'}]);
        expect(choices3).toEqual([{pk: 1, __str__: 'A'}, {pk: 2, __str__: 'B'}]);
    });

    it('renders choices correctly for multiple list items sharing the same cache', async () => {
        // This test simulates a queryset list page where multiple gorilla cards
        // each have a skills multi-select, and they should all share the same choices cache.

        // Clear choices cache to start fresh
        GlueFormProxy.choicesCache.clear();

        const skillsChoices = [
            {pk: 1, __str__: 'Chest Pound'},
            {pk: 2, __str__: 'Ground Slam'},
            {pk: 3, __str__: 'Tree Swing'},
        ];

        // Create mock http that returns choices
        const mockHttp = {
            sendAttributeEventRequest: mock(async () => ({
                data: {result: skillsChoices, state: {}},
            })),
        };

        // Create three "gorilla" proxies simulating queryset children
        // Each has different selected skills but same field definition
        const createGorillaProxy = (id, name, selectedSkills) => {
            const policy = createFormPolicy({
                name: `gorillas__${id}`,
                subject_details: {
                    model_class_path: 'gorilla.models.Gorilla',
                    included_fields: {
                        name: {type: 'CharField', label: 'Name'},
                        skills: {type: 'ModelMultipleChoiceField', label: 'Skills'},
                    },
                },
            });
            return new GlueFormProxy({
                http: mockHttp,
                name: `gorillas__${id}`,
                policy,
                state: createState({name, skills: selectedSkills}),
            });
        };

        const gorilla1 = createGorillaProxy(1, 'Brutus', [{pk: 1, __str__: 'Chest Pound'}]);
        const gorilla2 = createGorillaProxy(2, 'Grit', [{pk: 2, __str__: 'Ground Slam'}, {pk: 3, __str__: 'Tree Swing'}]);
        const gorilla3 = createGorillaProxy(3, 'Basher', []);

        // Render a list of gorilla cards, each with skills checkboxes
        const renderGorillaList = (gorillas) => {
            container.innerHTML = gorillas.map(gorilla => {
                const choices = gorilla.$fields.skills.choices || [];
                const selectedIds = (gorilla.skills || []).map(s => s.pk);
                return `
                    <div class="gorilla-card" data-id="${gorilla._name}">
                        <h3>${gorilla.name}</h3>
                        <div class="skills-summary">
                            ${selectedIds.length > 0
                                ? choices.filter(c => selectedIds.includes(c.pk)).map(c => c.__str__).join(', ')
                                : 'No skills selected'}
                        </div>
                        <div class="skills-checkboxes">
                            ${choices.map(choice => `
                                <label>
                                    <input type="checkbox" value="${choice.pk}"
                                        ${selectedIds.includes(choice.pk) ? 'checked' : ''} />
                                    ${choice.__str__}
                                </label>
                            `).join('')}
                        </div>
                    </div>
                `;
            }).join('');
        };

        // Initial render - choices not loaded yet
        renderGorillaList([gorilla1, gorilla2, gorilla3]);

        // Before choices load, cards with selected skills show empty (can't lookup names)
        // Only gorilla3 with no skills shows "No skills selected"
        const initialSummaries = container.querySelectorAll('.skills-summary');
        expect(initialSummaries[0].textContent.trim()).toBe(''); // Has skills but can't render names yet
        expect(initialSummaries[1].textContent.trim()).toBe(''); // Has skills but can't render names yet
        expect(initialSummaries[2].textContent.trim()).toBe('No skills selected'); // No skills

        // Wait for async choices to load
        await new Promise(resolve => setTimeout(resolve, 0));

        // Re-render after choices loaded
        renderGorillaList([gorilla1, gorilla2, gorilla3]);

        // Now each card should show the correct skills
        const summaries = container.querySelectorAll('.skills-summary');
        expect(summaries[0].textContent.trim()).toBe('Chest Pound');
        expect(summaries[1].textContent.trim()).toBe('Ground Slam, Tree Swing');
        expect(summaries[2].textContent.trim()).toBe('No skills selected');

        // Each card should have 3 checkboxes
        const cards = container.querySelectorAll('.gorilla-card');
        expect(cards[0].querySelectorAll('input[type="checkbox"]').length).toBe(3);
        expect(cards[1].querySelectorAll('input[type="checkbox"]').length).toBe(3);
        expect(cards[2].querySelectorAll('input[type="checkbox"]').length).toBe(3);

        // Verify correct checkboxes are checked for each gorilla
        const card1Checkboxes = cards[0].querySelectorAll('input[type="checkbox"]');
        expect(card1Checkboxes[0].checked).toBe(true);  // Chest Pound
        expect(card1Checkboxes[1].checked).toBe(false); // Ground Slam
        expect(card1Checkboxes[2].checked).toBe(false); // Tree Swing

        const card2Checkboxes = cards[1].querySelectorAll('input[type="checkbox"]');
        expect(card2Checkboxes[0].checked).toBe(false); // Chest Pound
        expect(card2Checkboxes[1].checked).toBe(true);  // Ground Slam
        expect(card2Checkboxes[2].checked).toBe(true);  // Tree Swing

        const card3Checkboxes = cards[2].querySelectorAll('input[type="checkbox"]');
        expect(card3Checkboxes[0].checked).toBe(false);
        expect(card3Checkboxes[1].checked).toBe(false);
        expect(card3Checkboxes[2].checked).toBe(false);

        // CRITICAL: Should only have made ONE request for choices (shared cache)
        expect(mockHttp.sendAttributeEventRequest).toHaveBeenCalledTimes(1);

        // All proxies should reference the same choices array
        expect(gorilla1.$fields.skills.choices).toBe(gorilla2.$fields.skills.choices);
        expect(gorilla2.$fields.skills.choices).toBe(gorilla3.$fields.skills.choices);
    });
});

/**
 * Tests for GlueFunctionProxy and GlueTemplateProxy DOM rendering.
 * These verify that function results and template HTML render correctly in the DOM,
 * simulating the Arena page behavior.
 */
describe('Function and Template Proxy DOM Rendering', () => {
    let container;

    beforeEach(() => {
        container = document.createElement('div');
        container.id = 'arena-test-container';
        document.body.appendChild(container);
    });

    afterEach(() => {
        container.remove();
    });

    it('renders function result data into the DOM', async () => {
        const {default: GlueFunctionProxy} = await import('../../src/proxies/function');
        const {createFunctionPolicy, createMockHttp} = await import('../testUtils');

        // Simulate calculate_fighter_rank function response
        const rankResult = {
            rank: 'Champion',
            tier: 'B',
            score: 6488,
            color: '#3498db',
            description: 'A proven champion ready for the biggest stages.',
        };

        const http = createMockHttp({
            result: {result: rankResult},
            state: null,
        });

        const calcRankFn = GlueFunctionProxy.create({
            http,
            name: 'calculate_fighter_rank',
            policy: createFunctionPolicy({
                subject_details: {
                    params: [
                        {name: 'rank_points'},
                        {name: 'age'},
                        {name: 'weight'},
                        {name: 'height'},
                    ],
                },
            }),
        });

        // Initial render - no result yet
        let result = null;
        const renderRankResult = () => {
            if (!result) {
                container.innerHTML = '<div class="rank-placeholder">Calculate rank...</div>';
                return;
            }
            container.innerHTML = `
                <div class="rank-result">
                    <span class="tier-badge" style="background-color: ${result.color}">${result.tier}</span>
                    <strong class="rank-name">${result.rank}</strong>
                    <p class="rank-description">${result.description}</p>
                    <span class="rank-score">Score: ${result.score}</span>
                </div>
            `;
        };

        renderRankResult();
        expect(container.querySelector('.rank-placeholder')).not.toBeNull();
        expect(container.querySelector('.rank-result')).toBeNull();

        // Call the function
        result = await calcRankFn({rank_points: 4657, age: 27, weight: 392, height: 1.4});

        // Re-render with result
        renderRankResult();

        expect(container.querySelector('.rank-placeholder')).toBeNull();
        expect(container.querySelector('.tier-badge').textContent).toBe('B');
        expect(container.querySelector('.rank-name').textContent).toBe('Champion');
        expect(container.querySelector('.rank-description').textContent).toBe(
            'A proven champion ready for the biggest stages.',
        );
        expect(container.querySelector('.rank-score').textContent).toBe('Score: 6488');
    });

    it('renders template HTML into the DOM via renderInnerHtml', async () => {
        const {default: GlueTemplateProxy} = await import('../../src/proxies/template');
        const {createTemplatePolicy, createMockHttp} = await import('../testUtils');

        const templateHtml = `
            <div class="rank-card">
                <div class="tier">A</div>
                <h4>Gorilla Grit</h4>
                <p>Elite fighter with exceptional skills.</p>
            </div>
        `;

        const proxy = new GlueTemplateProxy({
            http: createMockHttp({result: {html: templateHtml}, state: null}),
            name: 'rank_card',
            policy: createTemplatePolicy(),
        });

        // Create target element
        const target = document.createElement('div');
        target.id = 'rank-card-target';
        target.innerHTML = '<p>Placeholder content</p>';
        container.appendChild(target);

        expect(target.querySelector('.rank-card')).toBeNull();
        expect(target.querySelector('p').textContent).toBe('Placeholder content');

        // Render template into target
        await proxy.renderInnerHtml(target, {name: 'Gorilla Grit', tier: 'A'});

        expect(target.querySelector('.rank-card')).not.toBeNull();
        expect(target.querySelector('.tier').textContent).toBe('A');
        expect(target.querySelector('h4').textContent).toBe('Gorilla Grit');
    });

    it('replaces entire element with renderOuterHtml', async () => {
        const {default: GlueTemplateProxy} = await import('../../src/proxies/template');
        const {createTemplatePolicy, createMockHttp} = await import('../testUtils');

        const templateHtml = '<article class="new-element"><h2>Replaced!</h2></article>';

        const proxy = new GlueTemplateProxy({
            http: createMockHttp({result: {html: templateHtml}, state: null}),
            name: 'card',
            policy: createTemplatePolicy(),
        });

        const target = document.createElement('div');
        target.id = 'to-replace';
        target.innerHTML = '<p>Original</p>';
        container.appendChild(target);

        expect(container.querySelector('#to-replace')).not.toBeNull();
        expect(container.querySelector('.new-element')).toBeNull();

        await proxy.renderOuterHtml(target, {});

        // Original element should be gone, replaced by template output
        expect(container.querySelector('#to-replace')).toBeNull();
        expect(container.querySelector('.new-element')).not.toBeNull();
        expect(container.querySelector('.new-element h2').textContent).toBe('Replaced!');
    });

    it('sends correct attribute path to server for function execution', async () => {
        const {default: GlueFunctionProxy} = await import('../../src/proxies/function');
        const {createFunctionPolicy, createMockHttp} = await import('../testUtils');

        const http = createMockHttp({result: {result: 'intro text'}, state: null});
        const fn = GlueFunctionProxy.create({
            http,
            name: 'generate_introduction',
            policy: createFunctionPolicy({
                subject_details: {
                    params: [{name: 'name'}, {name: 'fight_style'}],
                },
            }),
        });

        await fn({name: 'Brutus', fight_style: 'aggressive'});

        const call = http.sendAttributeEventRequest.mock.calls[0][0];
        // CRITICAL: Must use full attribute path, not just 'execute'
        expect(call.attribute).toBe('GlueFunctionProxy.execute');
        expect(call.eventKwargs).toEqual({name: 'Brutus', fight_style: 'aggressive'});
    });

    it('sends correct attribute path to server for template rendering', async () => {
        const {default: GlueTemplateProxy} = await import('../../src/proxies/template');
        const {createTemplatePolicy, createMockHttp} = await import('../testUtils');

        const http = createMockHttp({result: {html: '<div>Test</div>'}, state: null});
        const proxy = new GlueTemplateProxy({
            http,
            name: 'test_template',
            policy: createTemplatePolicy(),
        });

        await proxy._renderHtml({context_var: 'value'});

        const call = http.sendAttributeEventRequest.mock.calls[0][0];
        // CRITICAL: Must use full attribute path, not just 'render_html'
        expect(call.attribute).toBe('GlueTemplateProxy.render_html');
        expect(call.eventKwargs).toEqual({context_var: 'value'});
    });
});
