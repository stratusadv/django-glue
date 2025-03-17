document.addEventListener('alpine:init', () => {
    Alpine.data('dropdown', () => ({
        open_dropdown: false,
        toggle_dropdown() {
            if (this.open_dropdown) {
                return this.close()
            }
            this.$refs.trigger.focus()
            this.open_dropdown = true
        },
        close(focusAfter) {
            if (!this.open_dropdown) return
            this.open_dropdown = false
            focusAfter && focusAfter.focus()
        },
        trigger: {
            ['x-ref']: 'trigger',
            ['@click']() {
                this.toggle_dropdown()
            },
            ['type']: 'button',
        },
        dialogue: {
            ['x-show']() {
                return this.open_dropdown
            },
            ['x-transition.origin.top.right']: '',
            ['@click.outside']() {
                this.open_dropdown = false
            },
        },
    }))
})

