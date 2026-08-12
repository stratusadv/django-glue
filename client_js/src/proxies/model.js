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

}

export default GlueModelProxy
