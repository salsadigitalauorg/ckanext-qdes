import ckan.plugins.toolkit as toolkit
import ckan.lib.uploader as uploader
import ckan.lib.navl.dictization_functions as df
import logging


log = logging.getLogger(__name__)


def validate_banner_image(key, flattened_data, errors, context):
    """
    Validates banner image, save the file and update the field.
    """
    # Get previous file, so we can remove it.
    banner_image = toolkit.config.get('ckanext.qdes.banner_image', '') or ''
    
    # Upload image.
    upload = uploader.get_uploader('qdes-admin', banner_image)
    upload.update_data_dict(flattened_data, ('ckanext.qdes.banner_image',),
                            ('banner_image_upload',), ('clear_banner_image_upload',))
    upload.upload(uploader.get_max_image_size())
