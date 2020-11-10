import logging
import ckan.plugins.toolkit as toolkit

from ckanext.qdes import helpers

get_action = toolkit.get_action
render = toolkit.render
log = logging.getLogger(__name__)


def review_datasets():
    site_user = get_action(u'get_site_user')({u'ignore_auth': True}, {})
    context = {u'user': site_user[u'name']}

    review_datasets = get_action('get_review_datasets')(context, {'dataset_review_period': helpers.qdes_get_dataset_review_period()})

    contact_points = {}
    for review_dataset in review_datasets:
        contact_point = review_dataset.get('contact_point', None)
        datasets = contact_points.get(contact_point, [])
        # Only add dataset if it does not already exist in datasets list
        title = review_dataset.get('title')
        name = review_dataset.get('name')
        url = toolkit.url_for('{}.read'.format(review_dataset.get('type', None)), id=name, _external=True)
        dataset = {'title': title, 'url': url}
        datasets.append(dataset) if dataset not in datasets else datasets
        contact_points[contact_point] = datasets

    for contact_point in contact_points:
        datasets = contact_points[contact_point]
        # Only email contact point if there are datasets
        if len(datasets) > 0:
            contact_point_data = get_action('get_secure_vocabulary_record')(context, {'vocabulary_name': 'point-of-contact', 'query': contact_point})
            if contact_point_data:
                recipient_name = contact_point_data.get('Name', '')
                recipient_email = contact_point_data.get('Email', '')
                subject = render('emails/subject/review_datasets.txt')
                body = render('emails/body/review_datasets.txt', {'datasets': datasets})
                body_html = render('emails/body/review_datasets.html', {'datasets': datasets})
                toolkit.enqueue_job(toolkit.mail_recipient, [recipient_name, recipient_email, subject, body, body_html])
