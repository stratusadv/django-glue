function isFieldMetadataProperty(prop) {
    return prop === 'choices'
        || prop === 'buildChoices'
        || prop === 'selectedChoice'
        || prop === 'selectedChoices'
        || prop === 'selectedPks'
        || prop === 'selectedLabel'
        || prop === 'pk'
        || (typeof prop === 'string' && prop.startsWith('__glue__'))
}

class FieldGlue {
    constructor({owner, name, metadata = {}}) {
        this.name = name
        Object.defineProperty(this, 'owner', {
            value: owner,
            enumerable: false,
            configurable: true,
        })
        this.updateMetadata(metadata)

        Object.defineProperty(this, '__glue__isFieldProxy', {
            value: true,
            enumerable: false,
            configurable: false,
        })
    }

    get value() {
        return this.owner._getFieldValue(this.name)
    }

    set value(value) {
        this.owner._setFieldValue(this.name, value)
    }

    get errors() {
        return this.owner._getFieldErrors()[this.name]
    }

    get hasErrors() {
        return Boolean(this.errors?.length)
    }

    updateMetadata(metadata = {}) {
        Object.entries(metadata).forEach(([key, value]) => {
            if (['value', 'errors', 'hasErrors'].includes(key)) {
                return
            }
            this[key] = value
        })
        this.name = this.name || metadata.name
    }

    primitiveValue(hint = 'default') {
        const value = this.value
        if (value === null || value === undefined) {
            return ''
        }
        if (value instanceof Date) {
            return hint === 'number' ? value.valueOf() : value.toString()
        }
        if (typeof value === 'object') {
            return Array.isArray(value) ? value.join(',') : String(value)
        }
        return value
    }

    [Symbol.toPrimitive](hint) {
        return this.primitiveValue(hint)
    }

    toString() {
        return String(this.primitiveValue())
    }

    valueOf() {
        return this.primitiveValue()
    }

    toJSON() {
        return this.value
    }

    asProxy() {
        const field = this
        return new Proxy(this, {
            get(target, prop, receiver) {
                if (prop === Symbol.iterator) {
                    return target.value?.[Symbol.iterator]?.bind(target.value)
                }
                if (prop === 'then') {
                    return undefined
                }
                if (
                    prop === 'choices'
                    && target.choice_model_path
                    && !target.__glue__choicesLoaded
                    && !target.__glue__loadingChoices
                ) {
                    target.ensureChoices([], receiver)
                }
                if (prop in target) {
                    return Reflect.get(target, prop, receiver)
                }

                const value = target.value
                const member = value?.[prop]
                return typeof member === 'function' ? member.bind(value) : member
            },
            set(target, prop, value, receiver) {
                if (prop === 'value') {
                    target.value = value
                    return true
                }
                if (prop in target || isFieldMetadataProperty(prop)) {
                    return Reflect.set(target, prop, value, receiver)
                }

                const current = target.value
                if (current && typeof current === 'object') {
                    current[prop] = value
                    return true
                }
                return Reflect.set(target, prop, value, receiver)
            },
            has(target, prop) {
                return prop in target || prop in Object(field.value ?? {})
            },
        })
    }
}

export default FieldGlue
