/**
 * Bun test setup file for DOM mocking.
 *
 * Note: window.location.reload() cannot be mocked in happy-dom.
 * Tests that need to verify reload behavior should spy on window.location.reload
 * within the test itself, or test the condition that triggers the reload.
 */

import { GlobalRegistrator } from '@happy-dom/global-registrator';

// Register happy-dom globals (document, window, fetch, etc.)
GlobalRegistrator.register();

// Note: window.confirm mock is set up in individual test files as needed
// since happy-dom provides its own implementation
