import ckan.plugins.toolkit as toolkit
import ckan.lib.api_token as api_token
import logging

log = logging.getLogger(__name__)


@toolkit.chained_action
def api_token_revoke(original_action, context, data_dict):
    # Get api_token object.
    model = context['model']
    token_obj = model.ApiToken.get(data_dict.get('jti'))

    # Exit early, not able to get token object.
    if token_obj:
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

    return original_action(context, data_dict)
