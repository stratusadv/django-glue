import GlueManager from './src/manager'

const Glue = new GlueManager()

window.Glue = Glue

queueMicrotask(() => Glue.init())