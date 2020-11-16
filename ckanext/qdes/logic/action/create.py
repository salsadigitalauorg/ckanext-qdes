
import ckan.plugins.toolkit as toolkit
import logging

from ckanext.qdes import jobs

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
