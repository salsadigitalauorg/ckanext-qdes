import ckan.plugins.toolkit as toolkit
import ckan.lib.api_token as api_token
import logging

from ckanext.qdes import jobs
from pprint import pformat

check_access = toolkit.check_access
log = logging.getLogger(__name__)


def review_datasets_job(context, data_dict):
    check_access('sysadmin', context)
    try:
        jobs.review_datasets(data_dict)
        return 'Successfully submitted review_datasets job'
    except Exception as e:
        log.error(e)
        return 'Failed to review_datasets job: {}'.format(e)


@toolkit.chained_action
def user_create(original_action, context, data_dict):
    data_dict['activity_streams_email_notifications'] = True
    return original_action(context, data_dict)


@toolkit.chained_action
def api_token_create(original_action, context, data_dict):
    result = original_action(context, data_dict)

    # Exit early, token create error.
    if not result.get('token', None):
        return result

    # Get api_token object.
    model = context['model']
    data = api_token.decode(result.get('token'))
    if not data or u"jti" not in data:
        return result

    token_obj = model.ApiToken.get(data[u"jti"])

    # Exit early, not able to get token object.
    if not token_obj:
        return result

    # You must be a sysadmin to create new activities. So we need to ignore auth check
    ignore_auth = context.get('ignore_auth', False)
    if ignore_auth == False:
        context['ignore_auth'] = True

    # Create activity.
    toolkit.get_action('activity_create')(context, {
        'user_id': token_obj.owner.id,
        'object_id': token_obj.owner.id,
        'activity_type': 'new API token',
        'data': {
            'token': dict(token_obj.as_dict()),
            'user': dict(token_obj.owner.as_dict())
        }
    })

    # If original ignore_auth value was set to false lets set it back to false to go down the chain
    if ignore_auth == False:
        context['ignore_auth'] = False

    return result
