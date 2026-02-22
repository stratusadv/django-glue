module.exports = {
    testEnvironment: 'node',
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
    coverageDirectory: 'coverage/js'
};
