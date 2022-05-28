import logging


def glue_ajax_handler_view(request):
    logging.warning('Glue Handler Start')
    logging.warning(f'{request.GET}')