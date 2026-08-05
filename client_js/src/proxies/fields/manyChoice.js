import ChoiceFieldGlue from "./choice"

class ManyChoiceFieldGlue extends ChoiceFieldGlue {
    get selectedValues() {
        return this.value || []
    }

    get selectedChoices() {
        const selectedValues = new Set(this.selectedValues.map(value => String(value)))
        return (this.choices || []).filter(choice => selectedValues.has(String(choice.value)))
    }

    hasChoiceSelected(value) {
        return this.selectedValues.some(item => String(item) === String(value))
    }

    addChoice(value) {
        if (this.hasChoiceSelected(value)) {
            return this
        }
        this.value = [...this.selectedValues, value]
        return this
    }

    removeChoice(value) {
        this.value = this.selectedValues.filter(item => String(item) !== String(value))
        return this
    }

    toggleChoice(value) {
        return this.hasChoiceSelected(value) ? this.removeChoice(value) : this.addChoice(value)
    }
}

export default ManyChoiceFieldGlue
