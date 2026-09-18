import FieldGlue from "./base"

class ChoiceFieldGlue extends FieldGlue {
    get selectedChoice() {
        return (this.choices || []).find(choice => String(choice.value) === String(this.value))
    }

    // Label of a choice, safe for assignment to innerHTML: fields configured
    // with a server-side label formatter (choices_label_is_html) carry
    // pre-rendered HTML, everything else is escaped plain text.
    choiceLabelHtml(choice) {
        const label = String(choice?.label ?? '')
        if (this.choices_label_is_html) {
            return label
        }
        return label
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
    }
}

export default ChoiceFieldGlue
