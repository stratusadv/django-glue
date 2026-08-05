import RelationFieldGlue from "./relation"

class ManyRelationFieldGlue extends RelationFieldGlue {
    get selectedPks() {
        return (this.value || []).filter(value => value != null)
    }

    get selectedChoices() {
        const selectedPks = new Set(this.selectedPks.map(value => String(value)))
        return (this.choices || []).filter(choice => selectedPks.has(String(choice.value)))
    }

    hasChoiceSelected(value) {
        return this.selectedPks.some(item => String(item) === String(value))
    }

    addChoice(value) {
        if (this.hasChoiceSelected(value)) {
            return this
        }
        this.value = [...(this.value || []), value]
        return this
    }

    removeChoice(value) {
        this.value = (this.value || []).filter(item => String(item) !== String(value))
        return this
    }

    toggleChoice(value) {
        return this.hasChoiceSelected(value) ? this.removeChoice(value) : this.addChoice(value)
    }
}

export default ManyRelationFieldGlue
