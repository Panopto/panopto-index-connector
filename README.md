# Panopto Index Connector

This public repository provides the framework for the Panopto Index Connector which powers federated search engine integrations. We recommend reading all documentation below before attempting to use the Panopto Index Connector.

- [License](#license)
- [Product Overview](#product-overview)
- [Installation](#installation)
- [The Panopto APIs](#the-panopto-apis)
- [Configuration and Usage Overview](#configuration-and-usage-overview)
- [Connector Implementations](#connector-implementations)
  - [Debug](#the-debug-implementation)
  - [Coveo](#the-coveo-implementation)
  - [Attivio](#the-attivio-implementation)
  - [Developing or Customizing Implementations](#developing-or-customizing-an-implementation)
- [Running the Connector](#running-the-connector)


## License

Copyright (c) 2020 Panopto, Inc.

Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance with the License. You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions and limitations under the License.

## Product Overview

This product will connect Panopto to your external search index. This can be done by either leveraging a current connector implementation, or creating your own (more on implementations below). The following sections cover how to install and run the Panopto Index Connector, how to configure an implementation for your schema, and how to develop a custom implementation if need be.

## Installation for Microsoft 365
Please follow [this document](https://docs.google.com/document/d/1CbnS4VnoKponmPx0CaxncpjPRpT7NEJ50XamLHTm4J4/edit?usp=sharing).

## Installation for platforms other than Microsoft 365

### Method 1: From official exe (recommended for out of the box)
If you do not need to create or customize a connector's implementation, and you are running on Windows, you may use the officially published `panopto-connector.exe` in the [releases tab](https://github.com/Panopto/panopto-index-connector/releases/). For other use cases, use methods 2 or 3.

### Method 2: From built exe (recommended for customizing/adding implementations)
If you need to add or customize an implementation (in a way that will not merge back to the public repository), then you will need to build your own executable. This can be done by working in a python3 environment and then running the following
```
git clone https://github.com/Panopto/panopto-index-connector.git <myfolder>
cd <myfolder>
pip install -e requirements.txt
pip install -e requirements.build.txt
python build_standalone.py
```

This will produce `dist\panopto-connector.exe` which may be copied to and run as a standalone application. Note that `build_standalone.py` will create a windows executable if run from a windows computer, and a linux executable if run from a linux computer.

### Method 3: Install via easy_setup (recommended for development)

To install the Panopto Index Connector, follow these steps

1. Install Python 3 (at least version 3.4)
2. Clone the github repo 
  - `git clone https://github.com/Panopto/panopto-index-connector.git <myfolder>`
3. Setup the connector by running the following from the cloned directory `<myfolder>`
  - `python setup.py install`

## Setup API Access

Configure a panopto user, e.g. "connector", which will be used for access to the API. Grant the user a user based API key. Grant the user permission to connect to the search index by navigating to Settings > Search-Engine Settings > User to Access Index Connector API. Add the user name you just configured (e.g. "connector").

![image](https://user-images.githubusercontent.com/4721718/197884016-bfdf1713-a29e-4d74-8aed-629658a2eb3a.png)


## The Panopto APIs

The panopto-index-connector leverages two Panopto endpoints -- the first one returns a list of video and playlist ids which need updating, and the second returns the content. This is all handled in the core part of the connector and will not require any configuration from the user. However, in the case that a user needs to build a custom solution or customize an existing solution, it is important to know the structure of the content response. Content returned from the Panopto API has the following form:

```json
"VideoContent": {
    // Content Management Data
    "Id": "33e14d6e-e814-4030-a9a4-fe5d14094c49",
    "Title": "(Playlist) My Playlist",
    "TypeName": "Panopto Playlist" | "Panopto Video", // one or the other
    "Url": "https://url-to-the-video",
    "ThumbnailUrl": "https://url-to-the-thumbnail",
    "Language": "English",

    // Flag to indicate if the video is deleted and should be removed from the external index
    "Deleted": false | true,

    // Metadata fields
    "Summary": "This is a summary of the playlist",
    "MachineTranscription": "I said these words which were captured by machine transcription",
    "HumanTranscription": "I said these words which were captured by human transcription",
    "ScreenCapture": "This text appeared on screen",
    "Presentation": "This text was in a powerpoint or keynote",

    // These users presented
    "Presenters": [
        {
            "Firstname": "Jane",
            "Lastname": "Doe",
            "Username": "janedoe"
        }
    ],

    // The users and groups allowed to search for this video
    "Principals": [
        {
            // Either Username and email will be present, or Groupname, on any principal but not both.
            // The Public Group is Groupname "Public Group"
            // Users/Groups created within Panopto will have "Panopto" as the identity provider.
            // If this user exists outside of the Panopto context, you will need some other way
            // to set the permission (like email)
            "Username": "janedoe",
            "Groupname": null,
            "IdentityProvider": "Panopto",
            "Email": "janedoe@organization.com"
        },
        {
            "Username": null,
            "Groupname": "MyGroup",
            "IdentityProvider": "Gsuite",
            "Email": null
        }
    ]
}
```

## Configuration and Usage Overview

The first step in configuring and running the connector is to get an authorized Panopto user account to run your connector. To authorize a user account to run the connector, contact Panopto Support with the user name you would like authorized. Then an admin user will generate an oauth key for that user.

Next we recommend running the [debug implementation](the-debug-implementation) before configuring your final implementation.

Next, you will choose a target index connector implementation. That will involve either using one of the predefined connector implementations, or developing your own. If choosing an existing implementation, you may need to make some custom code changes to it depending on your exact scenario. Finally, you will define your config file. See below for more details.

When you are ready to run the connector, you'll do so by running the following commandline: `panopto-index-connector -c <path-to-config-file>`. Once you have tested your connector, we recommend installing it as a service or daemon on the machine it will run on. 

See below on how to configure your implementation.

## Connector Implementations

Connector implementations live under the directory `src\panoptoindexconnector\implementations` and are named `*_implementation.py`. This section covers the existing implementations as well as how to develop your own.

**Note**: Even if you are using an existing implementation (e.g., the attivio_implementation) you may find it necessary to do some customization depending on your organization's permission structures, user mappings, or schema. We recommend all users who implement Federated Search Integrations read about their desired implementation and customizing an implementation.

### The debug implementation

This implementation, `debug_implementation.py`, prints the stream of incoming data to stdout for debugging purposes, and allows you to test your Panopto implementation. To use the debug implementation, you only need to fill in the first few values in `debug.yaml`, or define your own yaml config file. You'll need to define these values.

```yml
# The address to your panopto site
panopto_site_address: https://your.site.panopto.com

# The oauth credentials to connect to the panopto API
panopto_oauth_credentials:
    username: myconnectoruser
    password: mypassword
    client_id: 123
    client_secret: 456
    grant_type: password
```

Running the debug connector once you have configured your user and your oauth credentials is recommended to confirm that you are set up to correctly talk to the Panopto APIs, before continuing to your final implementation.

Other configuration options which are helpful to know about:
```yml
# Allows you to only send videos to the target matching one of a given permission set
# First bullet would only sync videos with view permission of a given Panopto groups
# The second for a given group from an external Identity provider
# The third would be only videos with panopto public permissions
# The fourth would be all authenticated users at your organization
principal_allowlist:
    - Group:Panopto:mygroup
    - Group:MyAdProvider:anothergroup
    - Group:Panopto:Public
    - Group:Panopto:All Users

# Default if empty or blank is false
# If true, tells the implementation to not push permissions
# Note this is only supported out of the box for coveo implementation
skip_permissions: true
```


### The Coveo implementation

The Coveo implementation works out of the box with your Coveo push source. You need to define your push source with the fields you select in the configuration of your configuration file. The template configuration file is `coveo.yaml`.

Create a copy of it and define the following. If you are on coveo cloud, you will not need to change the target address. Your credentials should include an api key to your push source with full access.

```yml
# Your index integration target endpoint
target_address: https://api.cloud.coveo.com

# Your coveo engine username/password for the connector
target_credentials:
    api_key: 00000000-0000-0000-0000-000000000000
    organization: acoveoorganization
    source: acoveoorganization-somethingorother
```

Then you define how to map the body elements of the panopto api response to fields in Coveo. Important notes:
- `Id: permanentid` This mapping should remain fixed, as permanentid is a predefined field in Coveo which remains static, even if the file uri changes.
- `Info: subelements` These mappings are standard fields in Coveo as well and should not change.
- `Metadata: subelements` These mappings you may define however you please. If you have defined the fields in Coveo, then they will ingest and be searchable based on the text fields. Any field you haven't defined will be ignored on indexing.

```yml
    # Id in panopto maps to permanentid in coveo
    Id: permanentid

    # Top level data
    Info:
        Title: title
        Language: language
        Url: uri

    # Content data
    Metadata:
        Summary: panopto_summary
        MachineTranscription: panopto_machine_transcription
        HumanTranscription: panopto_human_transcription
        ScreenCapture: panopto_screen_capture
        Presentation: panopto_presentation
        ThumbnailUrl: panopto_thumnail_url
```

### The Attivio implementation

The Attivio implementation, under `attivio_implementation.py`, works out of the box with the standard Attivio schema in 5.6.1. To configure this implementation, you'll need to define the Panopto configuration values as in the debug implementation, as well as these values in `attivio.yaml` (or a copy of it).

```yml
# Your attivio endpoint; 17000 is the attivio default port on deployed systems
target_address: https://myattivio.domain.local:17000

# Your search engine username/password for the connector
# This is the default password for the builtin admin, which
# may be fine for testing in your attivio development environment
target_credentials:
    username: aieadmin
    password: attivio
```

If your schema differs from the standard schema, you'll also need to update the field mapping section.

```yml
# Define the mapping from Panopto fields to Attivio fields
# This is set up to work on Attivio version 5 Default schema
field_mapping:

    # Id in panopto maps to id in attivio
    Id: id

    # Top level data
    Info:
        Title: title
        Language: language
        Url: uri
        ThumbnailUrl: img.uri.thumbnail

    # Content data
    Metadata:
        Summary: summary_text
        MachineTranscription: machine_transcription_text
        HumanTranscription: human_transcription_text
        ScreenCapture: screen_capture_text
        Presentation: presentation_text
```

It assumes that Panopto user names map to Attivio user names, as will be the case in the presence of a shared identity provider. The Panopto API returns the username, identity provider, and email of each user with permission to search for a given video, and you may need to customize the permissions handling in `attivio_implementation.py` to match your Attivio configuration (see [below](building-or-customizing-an-implementation)).

### The Microsoft Graph Connector implementation

The Microsoft Graph Connector implementation, under `microsoft_graph_implementation.py`, works out of the box with Microsoft 365.
To configure this implementation, please refer [this document](https://support.panopto.com/s/article/How-to-Set-Up-Panopto-Federated-Search-in-Microsoft-365).

### Developing or customizing an implementation

When creating or customizing an implementation, you can start by copying either an existing implementation and its config file, or to start from scratch, copy the template (`template_implementation.py` and `template.yaml`). For this tutorial, we'll call our implementation `my_implementation`.

First, we'll copy `template_implementation.py` to `my_implementation.py` and `template.yaml` to `my.yaml`.

First, fill in the top section of `my.yaml` with the Panopto configuration values. Update the `target_implementation` field to your implementation's name, as such.

```yml
# The address to your panopto site
panopto_site_address: https://your.site.panopto.com

# The oauth credentials to connect to the panopto API
panopto_oauth_credentials:
    username: myconnectoruser
    password: mypassword
    client_id: 123
    client_secret: 456
    grant_type: password

target_address: https://my.domain.local:12345/extra-url/paths

# This is a free form field; add or remove entries depending on your
# custom solution's security configuration
target_credentials:
    username: myuser
    password: mypassword

# Call this whatever your implementation is named; it controls
# the dependency injection
target_implementation: my_implementation
```

If the `field_mapping` section of `my.yaml` is helpful in organizing your custom solution, feel free to use it. Otherwise, you may define it as `field_mapping: None`

Now that our config file is defined, let's write our custom implementation. Open up `my_implementation.py`. There are three functions which need to be defined.

```py
def convert_to_target(panopto_content, field_mapping):
    """
    Implement this method to convert from panopto content format to target format
    """

    raise NotImplementedError("This is only a template")


def push_to_target(target_content, target_address, target_credentials):
    """
    Implement this method to push converted content to the target
    """

    raise NotImplementedError("This is only a template")


def delete_from_target(video_id, target_address, target_credentials):
    """
    Implement this method to push converted content to the target
    """

    raise NotImplementedError("This is only a template")
```

The first function allows you to conceptually organize the conversion from the Panopto API format to your target content format. The `field_mapping` member will be the value in your config file, and may simply be ignored if you do not use it. 

The second function implements pushing content to your custom target. It contains the `target_content` (from the previous function), the target address (from the config file), and the target_credentials (from the config file) as a dictionary object.

The third implements deleting content by ID, and is similar, but contains only the video id instead of the full content.

## Taking it to production

To deploy to production, we recommend installing the connector as a service on an isolated production machine. The binary panopto-connector.exe may be run on any windows machine. If you install from source, the connector supports Python 3.7+ on windows.
