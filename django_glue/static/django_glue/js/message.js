const message_list = document.getElementById('django-glue-message-list')

function add_message(type, title, body) {
    const message_template = document.getElementById('django-glue-message-template')
    let node_message = message_template.content.cloneNode(true)
    node_message.getElementById('django-glue-message-title').innerText = title
    node_message.getElementById('django-glue-message-body').innerText = body
    message_list.prepend(node_message)
    let new_message = message_list.children[0]

    new_message.classList.toggle('django-glue-message-' + type)

    setTimeout(function (){
        new_message.classList.toggle('django-glue-message-fade')
    }, 2500)
    setTimeout(function (){
        new_message.remove()
    }, 3000)

}

export {add_message}