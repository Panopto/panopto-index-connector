"""
Methods for the connector application to convert and sync content to the target endpoint

Implement these methods for the connector application
"""

# Standard Library Imports
import json
import logging
import os
import time

# Third party
import requests
import msal

# Global constants
DIR = os.path.dirname(os.path.realpath(__file__))
LOG = logging.getLogger(__name__)
APP_TEMP_DIR = str.lower(DIR).replace("panoptoindexconnector\implementations", "")
TOKEN_CACHE = os.path.join(APP_TEMP_DIR, 'token_cache.bin')


#########################################################################
#
# Exported methods to implement
#
#########################################################################


def convert_to_target(panopto_content, config):
    """
    Convert Panopto content to target format
    """

    field_mapping = config.field_mapping
    video_content = panopto_content["VideoContent"]

    # Set main properties (id and value)
    target_content = set_main_fields_to_new_object(video_content)

    # Set property fields
    set_properties(field_mapping, panopto_content, target_content)

    # Set acl (account controll list)
    set_principals(config, panopto_content, target_content)

    LOG.debug('Converted document is %s', json.dumps(target_content, indent=2))

    return target_content


def push_to_target(target_content, config):
    """
    Push converted Panopto content to the target
    """

    # If target content is None (case when none of permissions are set skip sync)
    if not target_content:
        LOG.warn("Content has been skipped for sync to target")
        return

    content_id = target_content.get("id")

    LOG.info("Pushing content (%s) to target", content_id)

    # Get token
    access_token = get_access_token(config)

    # Set headers
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    target_address = config.target_address
    connection_id = config.target_connection["id"]

    url = f"{target_address}/{connection_id}/items/{content_id}"

    response = requests.put(url, headers=headers, json=target_content)

    if response.status_code == 200:
        LOG.info(f"Content ({content_id}) has been pushed to target!")
    else:
        LOG.error(f"Content ({content_id}) has NOT been pushed to target! " +
                  f"Target Content: {target_content}. Response: {response.text}")


def delete_from_target(video_id, config):
    """
    Delete Panopto content from the target
    """

    LOG.info(f"Deleting video from target by id: {video_id}")

    # Get token
    access_token = get_access_token(config)

    # Set headers
    headers = {
        'Authorization': f'Bearer {access_token}'
    }

    target_address = config.target_address
    connection_id = config.target_connection["id"]
    url = f"{target_address}/{connection_id}/items/{video_id}"

    response = requests.delete(url, headers=headers)

    if response.status_code == 200:
        LOG.info(f"Video ({video_id}) has been deleted from target!")
    elif response.status_code == 404:
        LOG.info(f"Video ({video_id}) not found to be delete from target!")


#
# Initialize and teardown steps here
#

def initialize(config):
    """
    Create connection and register schema if not exists
    """

    try:
        ensure_connection_availability(config)
    except Exception as ex:
        LOG.error(f'Error occurred while initializing graph connector!. Error: {ex}')
        raise


def teardown(config):
    """
    Delete token cache file
    """

    if os.path.exists(TOKEN_CACHE):
        os.remove(TOKEN_CACHE)


#########################################################################
#
# Local helpers
#
#########################################################################


def set_main_fields_to_new_object(video_content):
    """
    Set id and content properties to new object
    """

    return {
        "id": video_content["Id"],
        "content": {
            "type": "text",
            "value": "{0} {1}".format(video_content["Id"], video_content["Title"])
        }
    }


def set_properties(field_mapping, panopto_content, target_content):
    """
    Set properties
    """

    # Set properties from Info yaml
    target_content['properties'] = {
        field:  panopto_content['VideoContent'][key]
        for key, field in field_mapping['Info'].items()
        if panopto_content['VideoContent'][key]
    }

    # Set properties from Metadata yaml
    target_content["properties"].update({
        field: panopto_content['VideoContent'][key]
        for key, field in field_mapping['Metadata'].items()
        if panopto_content['VideoContent'][key]
    })


def set_principals(config, panopto_content, target_content):
    """
    Set principals - Everyone (in tenant), User or Group.
    If none of permissions are set, target_content will be set to None and skipped for sync
    """

    if not config.skip_permissions:
        if is_public_or_all_users_principals(panopto_content):
            set_principals_to_all(config, target_content)
        elif is_user_principals(panopto_content):
            set_principals_to_user(config, panopto_content, target_content)
    else:
        set_principals_to_all(config, target_content)

    if not target_content["acl"]:
        target_content = None

        LOG.warn("Target content will be skipped to push to target since none of permissions have applied!")


def get_unique_principals(panopto_content):
    """
    Get unique principals to avoid duplicate permissions on synced item
    """

    unique_content_principals = []

    for principal in panopto_content['VideoContent']['Principals']:
        if principal not in unique_content_principals:
            unique_content_principals.append(principal)

    return unique_content_principals


def get_unique_external_user_principals(panopto_content):
    """
    Get unique user not Panopto principals to avoid duplicate permissions on synced item
    """

    unique_external_user_principals = []

    for p in panopto_content['VideoContent']['Principals']:
        if (p not in unique_external_user_principals and
                p.get('Username') and p.get('Email') and
                p.get('IdentityProvider') and p.get('IdentityProvider') != 'Panopto'):

            unique_external_user_principals.append(p)

    return unique_external_user_principals


def is_public_or_all_users_principals(panopto_content):
    """
    Check if session contains Public or All Users group permission
    Returns: True or False
    """

    return any(
        principal.get('Groupname') == 'Public'
        or principal.get('Groupname') == 'All Users'
        for principal in get_unique_principals(panopto_content)
    )


def is_user_principals(panopto_content):
    """
    Check is session contains user non Panopto permission
    Returns: True or False
    """

    return bool(get_unique_external_user_principals(panopto_content))


def set_principals_to_all(config, target_content):
    """
    Set session permission to all users from tenant
    """

    target_content["acl"] = [{
        "type": "everyone",
        "value": config.target_credentials["tenant_id"],
        "accessType": "grant"
    }]


def set_principals_to_user(config, panopto_content, target_content):
    """
    Set session permission to user
    """

    target_content["acl"] = []

    for principal in get_unique_external_user_principals(panopto_content):
        aad_user_info = get_aad_user_info(config, principal)

        if aad_user_info:
            acl = {
                "type": "user",
                "value": aad_user_info["id"],
                "accessType": "grant"
            }
            target_content["acl"].append(acl)


def get_aad_user_info(config, principal):
    """
    Get user info from azure active directory by email
    Returns: If found returns json response, else returns None
    """

    # Get token
    token = get_access_token(config)

    # Set headers
    headers = {
        'Authorization': f'Bearer {token}'
    }

    url = "https://graph.microsoft.com/v1.0/users/{0}".format(
        principal.get("Email"))

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        return response.json()

    LOG.warn("Unable to get user's info by email: {0}. Response: {1}".format(principal.get("Email"), response.json()))

    return None


def ensure_connection_availability(config):
    """
    Ensure that connection is ready for syncing.
    If connection is not created, create connection.
    If connection is created but schema is not registered, register schema.
    """

    # Get connection if exists
    connection_response = get_connection(config)

    # If connection exists
    if connection_response.status_code == 200:
        # If connection is ready (contains already schema) return from methon
        if connection_response.json()["state"] == "ready":
            LOG.info("Connection is already created and Ready!")
            return

        # If connection limit exceeded inform user and return from method
        if connection_response.json()["state"] == "limitExceeded":
            LOG.warn("Connection is already created but LIMIT EXCEEDED! " +
                     "Connection quota must be extended to be able to push new items. " +
                     "Updating or deleting items will work.")
            return

        if connection_response.json()["state"] == "draft":
            LOG.info("Connection is already created but not ready (Schema is not registered).")

    # If connection doesn't exit create it
    elif connection_response.status_code == 404:
        create_connection(config)

    # Check if schema is registered for connection and register it if not
    ensure_schema_for_connection(config)


def get_access_token(config):
    """
    Get access token from cache or a new one
    """

    target_credentials = config.target_credentials

    client_id = target_credentials["client_id"]
    client_secret = target_credentials["client_secret"]
    authority_url = target_credentials["authority"]
    tenant_id = target_credentials["tenant_id"]
    scopes = target_credentials["scopes"]

    # Load access token from cache file
    token_cache = load_token_cache()

    auth_app = msal.ConfidentialClientApplication(
        client_id=client_id,
        client_credential=client_secret,
        authority=f"{authority_url}/{tenant_id}",
        token_cache=token_cache)

    # Try to get a token from cache
    response = auth_app.acquire_token_silent(scopes, account=None)

    # No cached token found. Create a new one
    if not response:
        response = auth_app.acquire_token_for_client(scopes)

    # Save token to cache file if modified
    save_token_cache(token_cache)

    return response['access_token']


def load_token_cache():
    """
    Load token from cache file
    """

    cache = msal.SerializableTokenCache()

    if os.path.exists(TOKEN_CACHE):
        with open(TOKEN_CACHE, "r") as tc:
            cache.deserialize(tc.read())

    return cache


def save_token_cache(cache: msal.token_cache.SerializableTokenCache):
    """
    Save token to cache file
    """

    if cache.has_state_changed:
        with open(TOKEN_CACHE, "w") as tc:
            tc.write(cache.serialize())


def get_connection(config):
    """
    Get connection
    Returns: Response
    """

    # Get token
    access_token = get_access_token(config)

    # Set headers
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    target_address = config.target_address
    connection_id = config.target_connection["id"]
    url = f"{target_address}/{connection_id}"

    return requests.get(url, headers=headers)


def create_connection(config):
    """
    Create connection
    Returns: Json response
    """

    LOG.info("Creating connection...")

    connection_data = config.target_connection

    # Get token
    access_token = get_access_token(config)

    # Set headers
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    body_data = {
        "id": connection_data["id"],
        "name": connection_data["name"],
        "description": connection_data["description"]
    }

    response = requests.post(config.target_address, headers=headers, json=body_data)

    if response.status_code != 201:
        LOG.error("Connection has not been created! %s", response.json())

    response.raise_for_status()

    LOG.info("Connection has been created!")

    return response.json()


def ensure_schema_for_connection(config):
    """
    Ensure schema for connection
    """

    schema_response = get_schema_for_connection(config)

    # Register schema if not found
    if schema_response.status_code == 404:
        register_schema_for_connection(config)


def get_schema_for_connection(config):
    """
    Get schema for connection
    Returns: Response
    """

    target_address = config.target_address
    target_connection_id = config.target_connection["id"]

    url = f"{target_address}/{target_connection_id}/schema"
    access_token = get_access_token(config)

    # Set headers
    headers = {
        'Authorization': f'Bearer {access_token}'
    }

    response = requests.get(url, headers=headers)

    return response


def register_schema_for_connection(config):
    """
    Register schema for connection
    Returns: Response
    """

    LOG.info("Registering schema, this may take a moment...")

    target_address = config.target_address
    target_connection_id = config.target_connection["id"]

    url = f"{target_address}/{target_connection_id}/schema"
    access_token = get_access_token(config)

    # Set headers
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    schema_path = os.path.join(APP_TEMP_DIR, 'graph_schema.json')

    with open(schema_path, "r") as schema_file:
        schema_json = json.load(schema_file)

        response = requests.post(url, headers=headers, json=schema_json)

        # Schema is accepted to be registered
        if response.status_code == 202:
            LOG.info("Schema has been posted and accepted!")

            # Check connection operation status until complete status, so we can proceed with sync
            check_connection_operation_status(config, response.headers["Location"])

        # If schema already exists but still not registered (409 - conflict)
        elif response.status_code == 409:
            LOG.info("Schema is already posted but still not registered. Please try later. %s", response.json())
        else:
            LOG.info("Error while registering connection schema. %s", response.json())

        response.raise_for_status()


def check_connection_operation_status(config, operation_url):
    """
    Registering schema may take time so we need to wait
    until the schema is registered and connection is ready for sync.
    """

    LOG.info("Checking connection operation status...It may take time until the schema is registered.")

    access_token = get_access_token(config)

    # Set headers
    headers = {
        'Authorization': f'Bearer {access_token}'
    }

    while True:
        response = requests.get(operation_url, headers=headers)
        response.raise_for_status()

        response_json = response.json()
        if response.status_code == 200 and response_json["status"] == "completed":
            LOG.info("Connection is ready!")
            break

        # Wait 3 seconds until next check
        time.sleep(3)
