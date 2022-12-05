import datetime
import hashlib
import hmac
import json
from datetime import datetime
from urllib.error import HTTPError
from urllib.request import urlopen, Request

from otree.settings import AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY


# Key derivation functions. See:
# http://docs.aws.amazon.com/general/latest/gr/signature-v4-examples.html#signature-v4-examples-python
def sign(key, msg):
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def getSignatureKey(key, date_stamp, regionName, serviceName):
    kDate = sign(('AWS4' + key).encode('utf-8'), date_stamp)
    kRegion = sign(kDate, regionName)
    kService = sign(kRegion, serviceName)
    kSigning = sign(kService, 'aws4_request')
    return kSigning


def call_api(operation: str, request_parameters: dict, *, use_sandbox: bool) -> dict:
    # ************* REQUEST VALUES *************

    if use_sandbox:
        host = 'mturk-requester-sandbox.us-east-1.amazonaws.com'
    else:
        host = 'mturk-requester.us-east-1.amazonaws.com'
    endpoint = f'https://{host}'

    service = 'mturk-requester'
    region = 'us-east-1'
    # POST requests use a content type header. For DynamoDB,
    # the content is JSON.
    content_type = 'application/x-amz-json-1.1'
    amz_target = f'MTurkRequesterServiceV20170117.{operation}'

    # Create a date for headers and the credential string
    t = datetime.utcnow()
    amz_date = t.strftime('%Y%m%dT%H%M%SZ')
    date_stamp = t.strftime('%Y%m%d')  # Date w/o time, used in credential scope

    # ************* TASK 1: CREATE A CANONICAL REQUEST *************
    # http://docs.aws.amazon.com/general/latest/gr/sigv4-create-canonical-request.html

    # Step 2: Create canonical URI--the part of the URI from domain to query
    # string (use '/' if no path)
    canonical_uri = '/'

    ## Step 3: Create the canonical query string. In this example, request
    # parameters are passed in the body of the request and the query string
    # is blank.
    canonical_querystring = ''

    # Step 4: Create the canonical headers. Header names must be trimmed
    # and lowercase, and sorted in code point order from low to high.
    # Note that there is a trailing \n.
    canonical_headers = (
        'content-type:'
        + content_type
        + '\n'
        + 'host:'
        + host
        + '\n'
        + 'x-amz-date:'
        + amz_date
        + '\n'
        + 'x-amz-target:'
        + amz_target
        + '\n'
    )

    # Step 5: Create the list of signed headers. This lists the headers
    # in the canonical_headers list, delimited with ";" and in alpha order.
    # Note: The request can include any headers; canonical_headers and
    # signed_headers include those that you want to be included in the
    # hash of the request. "Host" and "x-amz-date" are always required.
    # For DynamoDB, content-type and x-amz-target are also required.
    signed_headers = 'content-type;host;x-amz-date;x-amz-target'

    request_body = json.dumps(request_parameters).encode('utf8')
    # Step 6: Create payload hash. In this example, the payload (body of
    # the request) contains the request parameters.
    payload_hash = hashlib.sha256(request_body).hexdigest()

    # Step 7: Combine elements to create canonical request
    canonical_request = '\n'.join(
        [
            'POST',
            canonical_uri,
            canonical_querystring,
            canonical_headers,
            signed_headers,
            payload_hash,
        ]
    )

    # ************* TASK 2: CREATE THE STRING TO SIGN*************
    # Match the algorithm to the hashing algorithm you use, either SHA-1 or
    # SHA-256 (recommended)
    algorithm = 'AWS4-HMAC-SHA256'

    credential_scope = '/'.join([date_stamp, region, service, 'aws4_request'])
    string_to_sign = '\n'.join(
        [
            algorithm,
            amz_date,
            credential_scope,
            hashlib.sha256(canonical_request.encode('utf-8')).hexdigest(),
        ]
    )

    # ************* TASK 3: CALCULATE THE SIGNATURE *************
    # Create the signing key using the function defined above.
    signing_key = getSignatureKey(AWS_SECRET_ACCESS_KEY, date_stamp, region, service)

    # Sign the string_to_sign using the signing_key
    signature = hmac.new(
        signing_key, string_to_sign.encode('utf-8'), hashlib.sha256
    ).hexdigest()

    # ************* TASK 4: ADD SIGNING INFORMATION TO THE REQUEST *************
    # Put the signature information in a header named Authorization.

    authorization_header = f"{algorithm} Credential={AWS_ACCESS_KEY_ID}/{credential_scope}, SignedHeaders={signed_headers}, Signature={signature}"

    # For DynamoDB, the request can include any headers, but MUST include "host", "x-amz-date",
    # "x-amz-target", "content-type", and "Authorization". Except for the authorization
    # header, the headers must be included in the canonical_headers and signed_headers values, as
    # # Python note: The 'host' header is added automatically by the Python 'requests' library.
    headers = {
        'Content-Type': content_type,
        'X-Amz-Date': amz_date,
        'X-Amz-Target': amz_target,
        'Authorization': authorization_header,
    }

    request = Request(endpoint, headers=headers)
    try:
        resp = urlopen(request, data=request_body)
    except HTTPError as exc:
        # 2022-12-05: I used to use ['Message'],
        # but it seems this key is not always present.
        msg = json.loads(exc.read().decode('utf8'))
        raise MTurkError(msg)
    res_body = resp.read()
    return json.loads(res_body.decode("utf-8"))


class MTurkError(Exception):
    pass


class TurkClient:
    """
    - Make these separate methods so they are easier to mock individually
    - Put them under a class so that they are easier to patch (don't have to worry about
    how it's imported)

    Also, in the future we might add some state, e.g. persistent connection
    """

    @staticmethod
    def create_hit(request_params, *, use_sandbox):
        return call_api('CreateHIT', request_params, use_sandbox=use_sandbox)

    @staticmethod
    def list_assignments_for_hit(request_params, *, use_sandbox):
        return call_api(
            'ListAssignmentsForHIT', request_params, use_sandbox=use_sandbox
        )

    @staticmethod
    def reject_assignment(request_params, *, use_sandbox):
        return call_api('RejectAssignment', request_params, use_sandbox=use_sandbox)

    @staticmethod
    def approve_assignment(request_params, *, use_sandbox):
        return call_api('ApproveAssignment', request_params, use_sandbox=use_sandbox)

    @staticmethod
    def send_bonus(request_params, *, use_sandbox):
        return call_api('SendBonus', request_params, use_sandbox=use_sandbox)

    @staticmethod
    def update_expiration(request_params, *, use_sandbox):
        return call_api(
            'UpdateExpirationForHIT', request_params, use_sandbox=use_sandbox
        )

    @staticmethod
    def assign_qualification(request_params, *, use_sandbox):
        return call_api(
            'AssociateQualificationWithWorker', request_params, use_sandbox=use_sandbox
        )
