function updateTaskTitle(title, onSuccess, onError) {
    Glue.task.title = title
    Glue.task.save({onSuccess, onError})
}

function deleteTask(onSuccess, onError) {
    Glue.task.delete({onSuccess, onError})
}
