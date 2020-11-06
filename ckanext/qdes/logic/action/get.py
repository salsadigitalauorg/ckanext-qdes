import logging
import ckan.authz as authz
import ckan.plugins.toolkit as toolkit

from datetime import datetime
from dateutil.relativedelta import relativedelta
from sqlalchemy import func
from ckanext.qdes import helpers

get_action = toolkit.get_action
log = logging.getLogger(__name__)


def review_datasets(context, data_dict):
    if not authz.is_sysadmin(context.get('user')) and not authz.has_user_permission_for_some_org(context.get('user'), 'create_dataset'):
        return {'success': False, 'msg': toolkit._('Not authorized')}

    model = context['model']
    try:
        cls = model.PackageExtra
        dataset_review_period = data_dict.get('dataset_review_period', helpers.qdes_get_dataset_review_period())
        review_date = datetime.utcnow() - relativedelta(months=dataset_review_period)

        query = model.PackageExtra().Session.query(cls) \
            .filter(cls.key == 'metadata_review_date') \
            .filter(func.date(cls.value) >= func.date(review_date)) \
            .filter(cls.state == 'active')

        return [get_action('package_show')(context, {'id': package_extra.package_id, }) for package_extra in query.all()]
    except Exception as e:
        log.error(str(e))

    return []
