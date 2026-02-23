module.exports = {
    testEnvironment: 'jsdom',
    roots: ['<rootDir>/client_js'],
    testMatch: ['**/*.test.js'],
    transform: {
        '^.+\\.js$': 'babel-jest'
    },
    moduleFileExtensions: ['js'],
    collectCoverageFrom: [
        'client_js/src/**/*.js',
        '!client_js/src/index.js'
    ],
    coverageDirectory: 'coverage/js',
    coverageThreshold: {
        global: {
            branches: 60,
            functions: 70,
            lines: 70,
            statements: 70
        }
    },
    setupFilesAfterEnv: ['<rootDir>/client_js/tests/setup.js']
};
