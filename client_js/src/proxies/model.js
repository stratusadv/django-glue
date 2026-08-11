import FieldBackedGlueProxy from "./fieldBacked"

class GlueModelProxy extends FieldBackedGlueProxy {
    _configureAttributeInitializers() {
        super._configureAttributeInitializers()
        this._attributeBuilders.readonly = (owner, name, qualName) => {
            this._initializeReadOnlyAttribute(owner, name, qualName)
        }
    }

    _initializeReadOnlyAttribute(owner, attributeName, attributeQualName) {
        Object.defineProperty(owner, attributeName, {
            get() {
                const root = this.__glue__root || this
                return root._state?.[attributeQualName]?.value
            },
            enumerable: true,
            configurable: true,
        })
    }

    async delete() {
        const result = await this._callAttribute('delete')
        this.$collection?._removeModelProxy(this)
        return result
    }

    async load() {
        const result = await this._callAttribute('load')
        this.$collection?._updateModelProxy(this)
        return result
    }
}

export default GlueModelProxy
