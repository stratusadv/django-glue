import type {GlueValueAttributeSchema, GlueValueComputedData} from "../../wire"

// Where a value attribute reads and writes its value and reads its computed
// data: an address record, or one object-valued attribute of one (a form held
// as state).
interface GlueValueAttributeRecord {
    getValue(path: string): unknown
    setValue(path: string, value: unknown): void
    getValueComputedData(path: string): Partial<GlueValueComputedData>
}

// What a value attribute needs of the proxy that owns it.
interface GlueValueAttributeOwner {
    _record: GlueValueAttributeRecord
}

// A value attribute's server presentation: its static schema merged with its
// computed data.
type GlueValueAttributePresentation = Partial<GlueValueAttributeSchema & GlueValueComputedData>

interface GlueValueAttributeOptions {
    owner: GlueValueAttributeOwner
    name: string
    fieldPath?: string
    stateKey?: string
    presentation?: GlueValueAttributePresentation
}

// updatePresentation() copies the presentation onto the attribute, except the
// keys an attribute class defines itself.
interface GlueValueAttribute extends Omit<GlueValueAttributePresentation, 'errors' | 'choices'> {}

class GlueValueAttribute {
    name: string
    fieldPath: string
    stateKey: string
    declare owner: GlueValueAttributeOwner
    declare _presentationKeys: string[] | undefined
    declare readonly __glue__isValueAttribute: true

    constructor({owner, name, fieldPath = name, stateKey, presentation = {}}: GlueValueAttributeOptions) {
        this.name = name
        this.fieldPath = fieldPath
        this.stateKey = stateKey || name

        Object.defineProperty(this, 'owner', {
            value: owner,
            enumerable: false,
            configurable: true,
        })

        this.updatePresentation(presentation)

        Object.defineProperty(this, '__glue__isValueAttribute', {
            value: true,
            enumerable: false,
            configurable: false,
        })
    }

    get value(): unknown {
        return this.owner._record.getValue(this.stateKey)
    }

    set value(value: unknown) {
        this.owner._record.setValue(this.stateKey, value)
    }

    get errors(): string[] {
        return this.owner._record.getValueComputedData(this.fieldPath).errors || []
    }

    get hasErrors(): boolean {
        return Boolean(this.errors?.length)
    }

    get errorText(): string {
        return this.errors.join(', ')
    }

    // Server presentation lands as plain data properties and never writes
    // through or shadows a member the attribute class defines (errors,
    // choices, value...): those own client-side state that a refresh must not
    // reset.
    updatePresentation(presentation: GlueValueAttributePresentation = {}): void {
        const members = this as unknown as Record<string, unknown>
        for (const key of this._presentationKeys || []) delete members[key]
        const prototype = Object.getPrototypeOf(this)
        const assignable = Object.fromEntries(
            Object.entries(presentation).filter(([key]) => !(key in prototype))
        )
        Object.assign(this, assignable)
        this._presentationKeys = Object.keys(assignable)
    }

    primitiveValue(hint = 'default'): unknown {
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

    [Symbol.toPrimitive](hint: string): unknown {
        return this.primitiveValue(hint)
    }

    toString(): string {
        return String(this.primitiveValue())
    }

    valueOf(): unknown {
        return this.primitiveValue()
    }

    toJSON(): unknown {
        return this.value
    }
}

export type {
    GlueValueAttributeOptions,
    GlueValueAttributeOwner,
    GlueValueAttributePresentation,
    GlueValueAttributeRecord,
}
export default GlueValueAttribute
