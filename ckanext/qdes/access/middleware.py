import logging
import ckan.plugins.toolkit as toolkit
import ckan.authz as authz
import ckan.views.api as api

log = logging.getLogger(__name__)


def qdes_access_before_request():
    if toolkit.request.endpoint not in toolkit.aslist(toolkit.config.get('ckanext.qdes_access.allowed_cached_endpoints')):
        log.debug(f'Setting __no_cache__ for endpoint {toolkit.request.endpoint}')
        toolkit.request.environ['__no_cache__'] = True
    else:
        log.debug(f'Allowed cached endpoint {toolkit.request.endpoint}')
    if toolkit.current_user.is_anonymous and toolkit.request.endpoint not in toolkit.aslist(toolkit.config.get('ckanext.qdes_access.unauthenticated_allowed_endpoints')):
        if toolkit.request.endpoint.startswith('api'):
            log.warning(f'Unauthenticated access to {toolkit.request.endpoint}. Returning 403 Authorization Error.')
            return_dict = {}
            return_dict['error'] = {'__type': 'Authorization Error',
                                     'message': toolkit._('Access denied')}
            return_dict['success'] = False
            toolkit.request.environ['__no_cache__'] = True
            return api._finish(403, return_dict, content_type='json')
        else:
            unauthenticated_redirect_endpoint = toolkit.config.get('ckanext.qdes_access.unauthenticated_redirect_endpoint')
            log.warning(f'Unauthenticated access to {toolkit.request.endpoint}. Redirecting to {unauthenticated_redirect_endpoint} page.')
            toolkit.request.environ['__no_cache__'] = True
            return toolkit.redirect_to(unauthenticated_redirect_endpoint)
