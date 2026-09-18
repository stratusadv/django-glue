import FieldGlue from "./base"

class ChoiceFieldGlue extends FieldGlue {
    get selectedChoice() {
        return (this.choices || []).find(choice => String(choice.value) === String(this.value))
    }

    // Label of a choice, safe for assignment to innerHTML: choices whose
    // server-side label was rendered by a formatter carry has_html_label and
    // pass through as-is, everything else is escaped plain text.
    choiceLabelHtml(choice) {
        const label = String(choice?.label ?? '')
        if (choice?.has_html_label) {
            return label
        }
        return label
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
    }

    // Plain text content of a choice label, for inputs and other text-only
    // spots that cannot render HTML.
    choiceLabelText(choice) {
        return String(choice?.label ?? '').replace(/<[^>]*>/g, '')
    }
}

export default ChoiceFieldGlue
