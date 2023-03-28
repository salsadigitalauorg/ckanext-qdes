from os import environ

DEFAULT_DATASET_REVIEW_PERIOD = 12
TMP_PATH = environ.get('SRC_DIR', '/app/src') + '/ckanext-qdes/ckanext/qdes/tmp'
REPORT_PATH = environ.get('CKAN_STORAGE_PATH', '/app/filestore') + '/storage/reports'
