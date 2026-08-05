import FieldGlue from "./base"

class ChoiceFieldGlue extends FieldGlue {
    get selectedChoice() {
        return (this.choices || []).find(choice => String(choice.value) === String(this.value))
    }
}

export default ChoiceFieldGlue
