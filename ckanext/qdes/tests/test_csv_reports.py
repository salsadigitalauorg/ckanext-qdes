import csv
import os

import ckanext.qdes.helpers as helpers
import ckanext.qdes.logic.helpers.report_helpers as report_helpers


def test_invalid_uri_csv_row_pairs_fields_with_urls(monkeypatch):
    monkeypatch.setattr(
        report_helpers,
        'url_for',
        lambda endpoint, **kwargs: 'https://ckan.test/{}'.format(endpoint),
    )

    row = report_helpers.invalid_uri_csv_row(
        {
            'fields': ['Dataset URL', 'Resource URL'],
            'uris': ['https://example.com/dataset', 'https://example.com/resource'],
        },
        {
            'Name': 'Test Contact',
            'Email': 'test@example.com',
        },
        {
            'id': 'dataset-1',
            'name': 'dataset-one',
            'title': 'Dataset One',
            'type': 'dataset',
            'extras': {'contact_creator': 'Creator Name'},
            'organization': {'title': 'Org One'},
        },
        {
            'id': 'resource-1',
            'name': 'Resource One',
        },
    )

    assert row == {
        'Dataset name': 'Dataset One',
        'Link to dataset (URI)': 'https://ckan.test/dataset.read',
        'Resource name': 'Resource One',
        'Link to resource': 'https://ckan.test/dataset_resource.read',
        'Dataset creator': 'Creator Name',
        'Point of contact - name': 'Test Contact',
        'Point of contact - email': 'test@example.com',
        'Invalid URLs': [
            {'field': 'Dataset URL', 'url': 'https://example.com/dataset'},
            {'field': 'Resource URL', 'url': 'https://example.com/resource'},
        ],
        'Organisation name': 'Org One',
    }
