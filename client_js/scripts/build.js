const fs = require('fs');
const zlib = require('zlib');

require('dotenv').config({ path: 'development.env' })

const PACKAGE_ROOT = './django_glue/client'
const OUT_DIR = process.env.DJANGO_GLUE_JS_DIST_PARENT_DIR

if (! fs.existsSync(OUT_DIR)) {
    fs.mkdirSync(OUT_DIR, 0744);
}

// Go through each file in the package's "build" directory
// and use the appropriate bundling strategy based on its name.
fs.readdirSync(`./${PACKAGE_ROOT}/builds`).forEach(file => {
    bundleFile(file)
});

function bundleFile(file, ) {
    // Based on the filename, give esbuild a specific configuration to build.
    ({
        // This output file is meant to be loaded in a browser's <script> tag.
        'cdn.js': () => {
            build({
                entryPoints: [`./${PACKAGE_ROOT}/builds/${file}`],
                outfile: `${OUT_DIR}/${file}`,
                bundle: true,
                platform: 'browser',
                define: { CDN: 'true' },
            })

            // Build a minified version.
            build({
                entryPoints: [`./${PACKAGE_ROOT}/builds/${file}`],
                outfile: `${OUT_DIR}/${file.replace('.js', '.min.js')}`,
                bundle: true,
                minify: true,
                platform: 'browser',
                define: { CDN: 'true' },
            }).then(() => {
                printVersion()
                outputSize(`${OUT_DIR}/${file.replace('.js', '.min.js')}`)
            })

        },
        // This file outputs two files: an esm module and a cjs module.
        // The ESM one is meant for "import" statements (bundlers and new browsers)
        // and the cjs one is meant for "require" statements (node).
        'module.js': () => {
            build({
                entryPoints: [`./${PACKAGE_ROOT}/builds/${file}`],
                outfile: `${OUT_DIR}/${file.replace('.js', '.esm.js')}`,
                bundle: true,
                platform: 'neutral',
                mainFields: ['module', 'main'],
            })

            build({
                entryPoints: [`./${PACKAGE_ROOT}/builds/${file}`],
                outfile: `${OUT_DIR}/${file.replace('.js', '.cjs.js')}`,
                bundle: true,
                target: ['node10.4'],
                platform: 'node',
            })
        },
    })[file]()
}

function build(options) {
    options.define || (options.define = {})

    options.define['GLUE_VERSION'] = getPythonConstantAsJsonValue('__VERSION__')
    options.define['process.env.NODE_ENV'] = process.argv.includes('--watch') ? `'production'` : `'development'`
    options.define['BASE_URL_NAME'] = getPythonConstantAsJsonValue('BASE_URL_NAME')

    return require('esbuild').build({
        logLevel: process.argv.includes('--watch') ? 'info' : 'warning',
        watch: process.argv.includes('--watch'),
        // external: ['alpinejs'],
        ...options,
    }).catch(() => process.exit(1))
}

function printVersion() {
    console.log("\x1b[32m", `django-glue version: ${getPythonConstantAsJsonValue('__VERSION__')}`)
}

function outputSize(file) {
    let size = bytesToSize(zlib.brotliCompressSync(fs.readFileSync(file)).length)
    console.log("\x1b[32m", `django-glue size: ${size}`)
}

function bytesToSize(bytes) {
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB']
    if (bytes === 0) return 'n/a'
    const i = parseInt(Math.floor(Math.log(bytes) / Math.log(1024)), 10)
    if (i === 0) return `${bytes} ${sizes[i]}`
    return `${(bytes / (1024 ** i)).toFixed(1)} ${sizes[i]}`
}

function getPythonConstantAsJsonValue(name) {
    // Read the Python file
    const constantsDotPyContent = fs.readFileSync('./django_glue/constants.py', 'utf8');


    // Parse the content to find variable assignments
    // This is a simplified example - real parsing would be more complex
    const lines = constantsDotPyContent.split('\n');
    let value;

    for (const line of lines) {
        // Look for lines matching your pattern
        if (line.includes(name)) {
            const match = line.match(new RegExp(`${name}\\s*=\\s*['"](.*?)['"]`));
            if (match) {
                value = match[1];
                break;
            }
        }
    }


    return `'${value}'`;
}