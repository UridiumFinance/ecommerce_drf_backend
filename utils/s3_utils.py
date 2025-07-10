import logging
import datetime

from django.utils import timezone
from django.conf import settings
from botocore.signers import CloudFrontSigner
from botocore.exceptions import ClientError
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding

logger = logging.getLogger(__name__)


def generate_presigned_url(s3_client, client_method, method_parameters, expires_in):
    """
    Generate a presigned Amazon S3 URL that can be used to perform an action.

    :param s3_client: A Boto3 Amazon S3 client.
    :param client_method: The name of the client method that the URL performs.
    :param method_parameters: The parameters of the specified client method.
    :param expires_in: The number of seconds the presigned URL is valid for.
    :return: The presigned URL.
    """
    try:
        url = s3_client.generate_presigned_url(
            clientMethod=client_method,
            Params=method_parameters,
            ExpiresIn=expires_in
        )
        logger.info("Got presigned URL: %s", url)
    except ClientError:
        logger.exception("Couldn't get a presigned URL for client method '%s'.", client_method)
        raise
    return url

def rsa_signer(message):
    # Load the private key from the string in Django settings
    private_key = serialization.load_pem_private_key(
        settings.AWS_CLOUDFRONT_KEY,  # Directly use the key from settings
        password=None,  # No password is assumed; adjust if your key is password-protected
        backend=default_backend()
    )
    # Sign the message
    signature = private_key.sign(
        message,
        padding.PKCS1v15(),
        hashes.SHA1()
    )
    # Return the base64-encoded signature
    return signature

def get_cloudfront_signed_url(key: str, expires_in=60):
    """
    Generates a CloudFront signed URL for a given S3 key.
    """
    if not key:
        return None

    url = f"https://{settings.AWS_CLOUDFRONT_DOMAIN}/{key}"
    key_id = settings.AWS_CLOUDFRONT_KEY_ID
    signer = CloudFrontSigner(key_id, rsa_signer)
    expire_date = timezone.now() + datetime.timedelta(seconds=expires_in)
    return signer.generate_presigned_url(url, date_less_than=expire_date)