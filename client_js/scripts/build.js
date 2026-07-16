import fs from 'fs'
import zlib from 'zlib'

const ENTRYPOINT_FILE_NAME = 'django_glue.js'
const ENTRYPOINT = `./client_js/${ENTRYPOINT_FILE_NAME}`
const OUT_DIR = './django_glue/static/django_glue/js'
const OUT_FILE_NAME = 'django_glue.js'
const OUT_FILE_PATH = `${OUT_DIR}/${OUT_FILE_NAME}`

if (!fs.existsSync(OUT_DIR)) {
    fs.mkdirSync(OUT_DIR, {recursive: true})
}

await build({minify: false, naming: OUT_FILE_NAME})
await build({minify: true, naming: OUT_FILE_NAME.replace('.js', '.min.js')})

outputSize(OUT_FILE_PATH.replace('.js', '.min.js'))

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
            'process.env.NODE_ENV': "'production'",
        },
    })

    if (!result.success) {
        for (const log of result.logs) {
            console.error(log)
        }
        process.exit(1)
    }
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
