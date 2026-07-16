import FieldBackedGlueProxy from "./fieldBacked"

class GlueFormProxy extends FieldBackedGlueProxy {
    async validate() {
        return await this._call('validate')
    }

    async save() {
        return await this._call('save')
    }
}

export default GlueFormProxy
