import type {GlueChoice} from "../../wire"
import ChoiceFieldGlue from "./choice"

class ManyChoiceFieldGlue extends ChoiceFieldGlue {
    get selectedValues(): unknown[] {
        return (this.value || []) as unknown[]
    }

    get selectedChoices(): GlueChoice[] {
        const selectedValues = new Set(this.selectedValues.map(value => String(value)))
        return (this.choices || []).filter(choice => selectedValues.has(String(choice.value)))
    }

    hasChoiceSelected(value: unknown): boolean {
        return this.selectedValues.some(item => String(item) === String(value))
    }

    addChoice(value: unknown): this {
        if (this.hasChoiceSelected(value)) {
            return this
        }
        this.value = [...this.selectedValues, value]
        return this
    }

    removeChoice(value: unknown): this {
        this.value = this.selectedValues.filter(item => String(item) !== String(value))
        return this
    }

    toggleChoice(value: unknown): this {
        return this.hasChoiceSelected(value) ? this.removeChoice(value) : this.addChoice(value)
    }
}

export default ManyChoiceFieldGlue
