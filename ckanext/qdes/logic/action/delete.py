import ckan.plugins.toolkit as toolkit
import logging


log = logging.getLogger(__name__)

@toolkit.chained_action
def api_token_revoke(original_action, context, data_dict):
    log.debug("Revoking token from qdes ...")
    return original_action(context, data_dict)