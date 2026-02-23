/**
 * Jest setup file for DOM mocking.
 *
 * Note: window.location.reload() cannot be mocked in jsdom.
 * Tests that need to verify reload behavior should spy on window.location.reload
 * within the test itself, or test the condition that triggers the reload.
 */

// Mock confirm for session expiry tests
window.confirm = jest.fn(() => true);