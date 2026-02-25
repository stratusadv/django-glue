import fs from 'fs';
import zlib from 'zlib';

const ENTRYPOINT_FILE_NAME = 'glue.js'

const ENTRYPOINT = `./client_js/${ENTRYPOINT_FILE_NAME}`
const OUT_DIR = './django_glue/static/django_glue/js'
const OUT_FILE_PATH = `${OUT_DIR}/${ENTRYPOINT_FILE_NAME}`

const VERSION = getPythonConstantAsJsonValue('__VERSION__')
const BASE_URL = getPythonConstantAsJsonValue('BASE_URL_NAME')
const IS_WATCH = process.argv.includes('--watch')

if (!fs.existsSync(OUT_DIR)) {
    fs.mkdirSync(OUT_DIR, { recursive: true });
}

// Build non-minified version
await build({ minify: false, naming: '[name].js' })

// Build minified version
await build({ minify: true, naming: '[name].min.js' })

printVersion()
outputSize(`${OUT_FILE_PATH.replace('.js', '.min.js')}`)


async function build(options) {
    const result = await Bun.build({
        entrypoints: [ENTRYPOINT],
        outdir: OUT_DIR,
        naming: options.naming,
        minify: options.minify,
        target: 'browser',
        format: 'iife',
        define: {
            'CDN': 'true',
            'GLUE_VERSION': VERSION,
            'BASE_URL_NAME': BASE_URL,
            'process.env.NODE_ENV': IS_WATCH ? "'development'" : "'production'",
        },
    })

    if (!result.success) {
        for (const log of result.logs) {
            console.error(log)
        }
        process.exit(1)
    }
}

function printVersion() {
    console.log("\x1b[32m", `django-glue version: ${getPythonConstantAsJsonValue('__VERSION__')}`)
}

function outputSize(file) {
    const size = bytesToSize(zlib.brotliCompressSync(fs.readFileSync(file)).length)
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
    const constantsDotPyContent = fs.readFileSync('./django_glue/constants.py', 'utf8');

    const lines = constantsDotPyContent.split('\n');
    let value;

    for (const line of lines) {
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
