const fs = require('fs');
const zlib = require('zlib');

require('dotenv').config({ path: 'development.env' })

const ENTRYPOINT_FILE_NAME = 'glue.js'

const ENTRYPOINT = `./client_js/${ENTRYPOINT_FILE_NAME}`
const OUT_DIR = './django_glue/static/django_glue/js'
const OUT_FILE_PATH = `${OUT_DIR}/${ENTRYPOINT_FILE_NAME}`

const VERSION = getPythonConstantAsJsonValue('__VERSION__')

if (! fs.existsSync(OUT_DIR)) {
    fs.mkdirSync(OUT_DIR, 0744);
}

build({
    entryPoints: [ENTRYPOINT],
    outfile: OUT_FILE_PATH,
    bundle: true,
    platform: 'browser',
    define: { CDN: 'true' },
})

build({
    entryPoints: [ENTRYPOINT],
    outfile: OUT_FILE_PATH.replace('.js', '.min.js'),
    bundle: true,
    minify: true,
    platform: 'browser',
    define: { CDN: 'true' },
}).then(() => {
    printVersion()
    outputSize(`${OUT_FILE_PATH.replace('.js', '.min.js')}`)
})


function build(options) {
    options.define || (options.define = {})

    options.define['GLUE_VERSION'] = VERSION
    options.define['process.env.NODE_ENV'] = process.argv.includes('--watch') ? `'production'` : `'development'`
    options.define['BASE_URL_NAME'] = getPythonConstantAsJsonValue('BASE_URL_NAME')

    return require('esbuild').build({
        logLevel: process.argv.includes('--watch') ? 'info' : 'warning',
        watch: process.argv.includes('--watch'),
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