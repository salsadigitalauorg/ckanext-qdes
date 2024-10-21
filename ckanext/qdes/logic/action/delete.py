import ckan.plugins.toolkit as toolkit
import logging

log = logging.getLogger(__name__)


@toolkit.chained_action
def api_token_revoke(original_action, context, data_dict):
    # Get api_token object.
    model = context['model']
    token_obj = model.ApiToken.get(data_dict.get('jti'))

    # Exit early, not able to get token object.
    if token_obj:
        # You must be a sysadmin to create new activities. So we need to ignore auth check
        ignore_auth = context.get('ignore_auth', False)
        if ignore_auth == False:
            context['ignore_auth'] = True

        # Create activity.
        toolkit.get_action('activity_create')(context, {
            'user_id': token_obj.owner.id,
            'object_id': token_obj.owner.id,
            'activity_type': 'revoked API token',
            'data': {
                'token': dict(token_obj.as_dict()),
                'user': dict(token_obj.owner.as_dict())
            }
        })

        # If original ignore_auth value was set to false lets set it back to false to go down the chain
        if ignore_auth == False:
            context['ignore_auth'] = False

    return original_action(context, data_dict)
