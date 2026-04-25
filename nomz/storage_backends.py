from storages.backends.s3boto3 import S3Boto3Storage, S3ManifestStaticStorage


class StaticStorage(S3ManifestStaticStorage):
    """
    Hashed static filenames on S3 so deploys cache-bust (plain S3Boto3Storage
    keeps the same URL for main.css and browsers honor max-age=86400).
    """

    location = "static"
    default_acl = "public-read"
    file_overwrite = True


class PublicMediaStorage(S3Boto3Storage):
    location = "media"
    default_acl = "public-read"
    file_overwrite = False
