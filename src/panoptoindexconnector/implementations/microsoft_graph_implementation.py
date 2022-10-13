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

# Local
from panoptoindexconnector.custom_exceptions import CustomExceptions
from panoptoindexconnector.enums import UserGroupMapping, UsernameMapping

# Global constants
DIR = os.path.dirname(os.path.realpath(__file__))
LOG = logging.getLogger(__name__)
APP_TEMP_DIR = str.lower(DIR).replace("panoptoindexconnector\implementations", "")
TOKEN_CACHE = os.path.join(APP_TEMP_DIR, 'token_cache.bin')

# Stored users to prevent unnecessary API calls to get id
USERS = {}

# Stored user groups to prevent unnecessary API calls to get id
USER_GROUPS = {}

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
    principals_are_set = set_principals(config, panopto_content, target_content)

    # If none of principals are set to content
    #   1. If content is already synced, remove it from target since nobody should be able to get it in search result
    #   2. Set skip_sync property to skip pushing content to target
    if not principals_are_set:
        delete_content_from_target_if_exists(target_content, config)
        target_content["skip_sync"] = True

    LOG.debug('Converted document is %s', json.dumps(target_content, indent=2))

    return target_content


def push_to_target(target_content, config):
    """
    Push converted Panopto content to the target
    """

    if target_content.get("skip_sync"):
        LOG.warn("Content has been skipped for sync to target!")
        return

    content_id = target_content.get("id")

    LOG.info("Pushing content (%s) to target...", content_id)

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
    # If request is forbidden
    elif response.status_code == 403:
        error = response.json()["error"]

        if error and error.get("innerError"):
            innerError = error.get("innerError")
            if innerError.get('code') == "TenantQuotaExceeded":
                raise CustomExceptions.QuotaLimitExceededError(innerError.get("message"))

        log_error_for_not_pushed_content(content_id, target_content, response.text)
    else:
        log_error_for_not_pushed_content(content_id, target_content, response.text)


def delete_from_target(content_id, config):
    """
    Delete Panopto content from the target
    """

    LOG.info(f"Deleting content from target by id: {content_id}...")

    # Get token
    access_token = get_access_token(config)

    # Set headers
    headers = {
        'Authorization': f'Bearer {access_token}'
    }

    target_address = config.target_address
    connection_id = config.target_connection["id"]
    url = f"{target_address}/{connection_id}/items/{content_id}"

    response = requests.delete(url, headers=headers)

    if response.status_code == 200:
        LOG.info(f"Content ({content_id}) has been deleted from target!")
    elif response.status_code == 404:
        LOG.info(f"Content ({content_id}) not found to be delete from target!")


#
# Initialize and teardown steps here
#

def initialize(config):
    """
    Create connection and register schema if not exists
    """

    try:
        # Clear users list before each sync attempt to keep up to date AAD users info
        USERS.clear()

        # Clear user groups list before each sync attempt to keep up to date AAD user groups info
        USER_GROUPS.clear()

        # Validate microsoft_graph.yaml configuration file
        validate_configuration(config)

        # Ensure connection for sync
        ensure_connection_availability(config)
    except (CustomExceptions.ConfigurationError, CustomExceptions.QuotaLimitExceededError):
        # No need to log here since it will be logged in caller method ("run" method)
        raise
    except Exception as ex:
        LOG.error(f'Error occurred while initializing microsoft graph connector!. Error: {ex}')
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
    Returns: True if any of principals are set, otherwise False
    """

    principals_are_set = False

    set_public_or_all_users_principals = has_public_or_all_users_principals(panopto_content)
    set_user_principals = has_user_principals(config, panopto_content)
    set_user_group_principals = has_user_group_principals(config, panopto_content)

    if not config.skip_permissions:
        # Set public or all users grant principals if exist
        if set_public_or_all_users_principals:
            set_principals_to_all(config, target_content)
        # Set user and/or user group grant principals if exist
        elif set_user_principals or set_user_group_principals:
            target_content["acl"] = []

            if set_user_principals:
                set_principals_to_user(config, panopto_content, target_content)
            if set_user_group_principals:
                set_principals_to_user_group(config, panopto_content, target_content)
    else:
        set_principals_to_all(config, target_content)

    if target_content.get("acl"):
        principals_are_set = True
    else:
        LOG.warn("Content will be skipped to push to target since none of principals have applied!")

    return principals_are_set


def get_unique_principals(panopto_content):
    """
    Get unique principals to avoid duplicate principals on synced item
    """

    unique_content_principals = []

    for principal in panopto_content['VideoContent']['Principals']:
        if principal not in unique_content_principals:
            unique_content_principals.append(principal)

    return unique_content_principals


def get_unique_external_user_principals(config, panopto_content):
    """
    Get unique external Panopto principals to avoid duplicate principals on synced item.
    Identity provider will be matched with configured id provider instance name.
    """

    unique_external_user_principals = []

    for p in panopto_content['VideoContent']['Principals']:
        if (p not in unique_external_user_principals and
                p.get('Username') and
                p.get('IdentityProvider') and
                p.get('IdentityProvider').lower() ==
                ("unified" if config.panopto_id_provider_is_unified else config.panopto_id_provider_instance_name.lower())):

            unique_external_user_principals.append(p)

    return unique_external_user_principals


def get_unique_user_group_external_contexts(config, panopto_content):
    """
    Get unique user group external contexts to avoid duplicate principals on synced item.
    Identity provider will be matched with configured identity provider instance name.
    """

    unique_user_group_external_contexts = []

    # Get user group principals that contains ExternalContexts
    user_group_principals = [
        p for p in panopto_content['VideoContent']['Principals']
        if p.get('Groupname') and p.get('ExternalContexts')
    ]

    for p in user_group_principals:
        for ec in p.get('ExternalContexts'):
            if (ec not in unique_user_group_external_contexts and
                ec.get("ExternalId") and
                ec.get("IdentityProviderName") and
                ec.get("IdentityProviderName").lower() == config.panopto_id_provider_instance_name.lower()):

                unique_user_group_external_contexts.append(ec)

    return unique_user_group_external_contexts


def has_public_or_all_users_principals(panopto_content):
    """
    Check if session contains Public or All Users group permission
    Returns: True or False
    """

    return any(
        principal.get('Groupname') == 'Public'
        or principal.get('Groupname') == 'All Users'
        for principal in get_unique_principals(panopto_content)
    )


def has_user_principals(config, panopto_content):
    """
    Check is session contains user non Panopto permission
    Returns: True or False
    """

    return bool(get_unique_external_user_principals(config, panopto_content))


def has_user_group_principals(config, panopto_content):
    """
    Check is session contains user group permissions
    Returns: True or False
    """

    return bool(get_unique_user_group_external_contexts(config, panopto_content))


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

    for principal in get_unique_external_user_principals(config, panopto_content):

        panopto_username = get_panopto_username(principal)
        user_id = None

        # Try to get user id from users dictionary
        if panopto_username in USERS:
            user_id = USERS.get(panopto_username)
        # If user doesn't exist in dictionary, try to get from AAD calling API
        else:
            # Get user from AAD
            aad_user_info = get_aad_user_info(config, panopto_username)

            if aad_user_info:
                user_id = aad_user_info["id"]

            # Add user to list to prevent further API calls for the same user
            USERS[panopto_username] = user_id

        if user_id:
            acl = {
                "type": "user",
                "value": user_id,
                "accessType": "grant"
            }
            target_content["acl"].append(acl)


def set_principals_to_user_group(config, panopto_content, target_content):
    """
    Set session permission to user group
    """

    for ec in get_unique_user_group_external_contexts(config, panopto_content):

        # Set External Id from Group External Context
        panopto_user_group_identifier = ec.get("ExternalId")

        # Azure Active Directory Group Id
        aad_group_id = None

        # Try to get user group id from user_groups list
        if panopto_user_group_identifier in USER_GROUPS:
            aad_group_id = USER_GROUPS.get(panopto_user_group_identifier)
        # If user group doesn't exist in list, try to get from AAD calling API
        else:
            # Get user group from Azure Active Directory
            aad_user_group_info = get_aad_user_group_info(config, panopto_user_group_identifier)

            # If Azure Active Directory group has been retrieved by group identifier,
            # set Group Id and use it to grant group permission
            if aad_user_group_info:
                aad_group_id = aad_user_group_info["id"]

            # Add user group to USER_GROUPS list to prevent further API calls for the same user group
            USER_GROUPS[panopto_user_group_identifier] = aad_group_id

        if aad_group_id:
            acl = {
                "type": "group",
                "value": aad_group_id,
                "accessType": "grant"
            }
            target_content["acl"].append(acl)


def get_panopto_username(principal):
    """
    Get Panopto username from principal
    """

    panopto_username = principal.get("Username")
    if "\\" in panopto_username:
        panopto_username = panopto_username.split("\\")[1]

    return panopto_username


def get_aad_user_info(config, panopto_username):
    """
    Get user info from azure active directory by email
    Returns: If found returns json response, else returns None
    """

    aad_user_info = None

    # Get token
    token = get_access_token(config)

    # Set headers
    headers = {
        'Authorization': f'Bearer {token}'
    }

    # Set filter parameter to get azure AD user by userPrincipalName or mail
    params = {
        '$filter': f"{config.panopto_username_mapping} eq '{panopto_username}'"
    }

    url = "https://graph.microsoft.com/v1.0/users"

    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200:
        response_value = response.json().get("value")
        if response_value:
            # Filtered response returns list of values
            # but if we filter by userPrincipalName or mail
            # only one value can be returned, so we will take the first one
            aad_user_info = response_value[0]
    else:
        LOG.warn("Unable to get aad user's info by: {0}. Response: {1}".format(panopto_username, response.json()))

    return aad_user_info


def get_aad_user_group_info(config, panopto_user_group_identifier):
    """
    Get user group info from azure active directory by Panopto user group identifier
    Returns: If found returns json response, else returns None
    """

    aad_user_group_info = None

    # Get token
    token = get_access_token(config)

    # Set headers
    headers = {
        'Authorization': f'Bearer {token}'
    }

    # Set filter parameter to get azure AD user by 'id' or 'onPremisesSamAccountName'
    params = {
        '$filter': f"{config.panopto_user_group_mapping} eq '{panopto_user_group_identifier}'"
    }

    url = "https://graph.microsoft.com/v1.0/groups"

    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200:
        response_value = response.json().get("value")
        if response_value:
            # Filtered response returns list of values
            # but if we filter by id or onPremisesSamAccountName
            # only one value can be returned, so we will take the first one
            aad_user_group_info = response_value[0]
    else:
        LOG.warn(
            "Unable to get aad user group's info by: {0} eq {1}. Response: {2}."
            .format(config.panopto_user_group_mapping, panopto_user_group_identifier, response.json()))

    return aad_user_group_info


def validate_configuration(config):
    """
    Validate microsoft_graph.yaml configuration file
    """

    # Validate identity provider instance name - Must be set
    if not bool(config.panopto_id_provider_instance_name):
        raise CustomExceptions.ConfigurationError(
            """
            Configuration Error!
            Panopto identity provider instance name is not set!
            Please update your configuration file and set Panopto identity provider instance name
            (panopto_id_provider_instance_name) that will be used for matching users with target Tenant.
            """
        )

    # Validate username mapping attribute value - Must contains valid value
    username_mapping_attribute = config.panopto_username_mapping
    username_mapping_enum_values = set(item.value for item in UsernameMapping)

    if username_mapping_attribute not in username_mapping_enum_values:
        raise CustomExceptions.ConfigurationError(
            """
            Configuration Error!
            Panopto username mapping attribute value '{0}' is not valid!
            Please update your configuration file and set Panopto username mapping
            (panopto_username_mapping) with valid value: 'userPrincipalName' or 'mail' (Case sensitive).
            """.format(username_mapping_attribute)
        )

    # Validate username mapping attribute value - Must contains valid value
    user_group_mapping_attribute = config.panopto_user_group_mapping
    user_group_mapping_enum_values = set(item.value for item in UserGroupMapping)

    if user_group_mapping_attribute not in user_group_mapping_enum_values:
        raise CustomExceptions.ConfigurationError(
            """
            Configuration Error!
            Panopto user group mapping attribute value '{0}' is not valid!
            Please update your configuration file and set Panopto user group mapping
            (panopto_user_group_mapping) with valid value: 'id' or 'onPremisesSamAccountName' (Case sensitive).
            """.format(user_group_mapping_attribute)
        )


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

        # If connection limit exceeded inform user and stop further processing by raising error
        if connection_response.json()["state"] == "limitExceeded":
            LOG.error("Connection is already created but LIMIT EXCEEDED!")

            raise CustomExceptions.QuotaLimitExceededError(
                "Tenant quota has been reached! " +
                "To continue adding items to the connection the tenant admin must contact Microsoft or delete some content."
            )

        if connection_response.json()["state"] == "draft":
            LOG.info("Connection is already created but not ready (Schema is not registered).")

    # If request is Unauthorized
    elif connection_response.status_code == 401:
        LOG.error("Unable to get connection because of Unauthorized request!. " +
                  "Please check if Client contains 'ExternalConnection.ReadWrite.OwnedBy' and " +
                  "'ExternalItem.ReadWrite.OwnedBy' API permissions.")

        connection_response.raise_for_status()

    # If connection doesn't exit create it
    elif connection_response.status_code == 404:
        LOG.info("Connection doesn't exist!")
        create_connection(config)

    else:
        connection_response.raise_for_status()

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

    LOG.info("Getting connection: %s", config.target_connection["id"])

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

    schema_path = os.path.join(APP_TEMP_DIR, 'microsoft_graph_schema.json')

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


def log_error_for_not_pushed_content(content_id, target_content, response_text):
    """
    Logs error for not pushed content to target
    """

    LOG.error(f"Content ({content_id}) has NOT been pushed to target! " +
              f"Target Content: {target_content}. Response: {response_text}")


def delete_content_from_target_if_exists(target_content, config):
    """
    Delete content from target if exists (already synced)
    """

    content_id = target_content.get("id")

    LOG.info(f"Checking if content ({content_id}) is already synced in order to delete from target "
              "since none of principals are applied to content...")

    content_from_target = get_content_from_target(content_id, config)

    if content_from_target:
        LOG.info(f"Content ({content_id}) is already synced and we will proceed with deleting from target!")
        delete_from_target(content_id, config)


def get_content_from_target(content_id, config):
    """
    Get content from target
    """

    LOG.info(f"Getting content from target by id: {content_id}...")

    content_from_target = None

    # Get token
    access_token = get_access_token(config)

    # Set headers
    headers = {
        'Authorization': f'Bearer {access_token}'
    }

    target_address = config.target_address
    connection_id = config.target_connection["id"]
    url = f"{target_address}/{connection_id}/items/{content_id}"

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        content_from_target = response.json()
    elif response.status_code == 404:
        LOG.info(f"Content ({content_id}) not found from target!")

    return content_from_target
