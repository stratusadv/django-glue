import FieldGlue from "./base"

class ChoiceFieldGlue extends FieldGlue {
    get selectedChoice() {
        return (this.choices || []).find(([value]) => value === this.value)
    }

    get selectedLabel() {
        return this.selectedChoice?.[1] ?? ''
    }
}

export default ChoiceFieldGlue
