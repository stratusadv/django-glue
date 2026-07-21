import FieldGlue from "./base"

class ChoiceFieldGlue extends FieldGlue {
    get selectedChoice() {
        return (this.choices || []).find(([value]) => String(value) === String(this.value))
    }

    get selectedLabel() {
        return this.selectedChoice?.[1] ?? ''
    }
}

export default ChoiceFieldGlue
