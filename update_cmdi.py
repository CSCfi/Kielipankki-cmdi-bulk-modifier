import difflib
import json
import pathlib

import click
import lxml
import requests
from sickle import Sickle

from modifiers.lb_modifiers import (
    UhelDistributionRightsHolderModifier,
    AddOrganizationForPersonModifier,
    FinclarinPersonToOrganizationModifier,
    LanguageBankPersonToOrganizationModifier,
    AddCreatorFromJsonModifier,
)


class UploadError(Exception):
    """
    For reporting errors in COMEDI uploads
    """


def cmdi_records(repository_url, set_id):
    """
    Iterate all records of a given set in a given repository
    """
    sickle = Sickle(repository_url)
    metadata_records = sickle.ListRecords(
        **{
            "metadataPrefix": "cmdi",
            "set": set_id,
        }
    )
    for record in metadata_records:
        yield record.xml


def selected_modifiers(click_context):
    """
    Return a list of modifiers the user has selected using flags.
    """
    modifiers = []

    if click_context.params["add_affiliations_from"]:

        affiliation_filename = click_context.params["add_affiliations_from"]
        with open(affiliation_filename, "r") as affiliation_file:
            affiliations = json.loads(affiliation_file.read())
            for affiliation in affiliations:
                modifiers.append(
                    AddOrganizationForPersonModifier(
                        first_name=affiliation["first_name"],
                        surname=affiliation["last_name"],
                        organization_info_str=affiliation["organization_info_str"],
                    )
                )

    if click_context.params["add_creators_from"]:
        creator_filename = click_context.params["add_creators_from"]
        with open(creator_filename, "r") as creator_file:
            creators = json.loads(creator_file.read())
            modifiers.append(
                AddCreatorFromJsonModifier(
                    creator_dicts=creators,
                )
            )

    if click_context.params["finclarin_to_organization"]:
        modifiers.append(FinclarinPersonToOrganizationModifier())

    if click_context.params["language_bank_to_organization"]:
        modifiers.append(LanguageBankPersonToOrganizationModifier())

    if click_context.params["uhel_distribution_rights_holder_for"]:
        identifier_filename = click_context.params[
            "uhel_distribution_rights_holder_for"
        ]
        with open(identifier_filename, "r") as identifier_file:
            identifiers = [
                identifier.strip() for identifier in identifier_file.readlines()
            ]
        modifiers.append(UhelDistributionRightsHolderModifier(identifiers))

    return modifiers


def short_identifier_from_pid(pid):
    """
    Return short identifier (e.g. lb-123) from pid (e.g. urn:nbn:fi:lb-123).
    """
    identifier = pid.split(":")[-1]
    parts = identifier.split("-")
    if parts[0] != "lb":
        raise ValueError(
            f"Unexpected PID format {pid} encountered: last part does not start with 'lb-'"
        )
    try:
        int(parts[1])
    except ValueError:
        raise ValueError(
            f"Unexpected PID format {pid} encountered: does not end with a number"
        )
    return identifier


def replace_record(api_url, pid, session_id, record):
    """
    Delete old record and reupload with updated data.

    All records are set to published, because the records are iterated without providing
    "status" parameter to the OAI-PMH API, thus producing only published records from
    Comedi (and likely all other OAI-PMH APIs too, as unpublished records and the
    associated status are Comedi specialities).
    """
    short_identifier = short_identifier_from_pid(pid)
    delete_record(api_url, short_identifier, session_id)
    upload_record(api_url, short_identifier, session_id, record, True)


def delete_record(api_url, short_identifier, session_id):
    """
    Delete a record from COMEDI.
    """
    requests.get(
        f"{api_url}/rest?command=delete-record",
        params={"session-id": session_id, "identifier": short_identifier},
    )


def upload_record(api_url, short_identifier, session_id, record, published):
    """
    Upload the given XML record, using only the last part of the PID (e.g. lb-1234) as the
    identifier.
    """

    params = {
        "group": "FIN-CLARIN",
        "session-id": session_id,
        "identifier": short_identifier,
    }
    if published:
        params["published"] = published

    response = requests.post(
        f"{api_url}/upload",
        params=params,
        files={
            "file": (f"{short_identifier}.xml", lxml.etree.tostring(record), "text/xml")
        },
    )
    response.raise_for_status()

    if "error" in response.json():
        raise UploadError(
            f"Upload of {short_identifier} failed: {response.json()['error']}"
        )
    if "success" not in response.json() or not response.json()["success"]:
        raise UploadError(
            "Something went wrong when uploading {schort_identifier}: {response.json()}"
        )


def xml_string_diff(original_record_string, modified_record_string):
    """
    Determine the diff between two XML strings.

    The strings should be pretty-printed to allow for neat diff when doing line-by-line
    comparison.

    :param original_record_string: The orifinal XML as pretty-printed string
    :type original_record_string: str
    :param modified_record_string: The modified XML as pretty-printed string
    :type modified_record_string: str
    :returns: String representation of the diff for displaying to user
    """
    original_lines = original_record_string.split("\n")
    modified_lines = modified_record_string.split("\n")
    diff_lines = difflib.context_diff(
        original_lines, modified_lines, fromfile="original", tofile="modified", n=6
    )
    return "\n".join(diff_lines)


# some of the arguments are parsed via click context passed to `selected_modifiers`
# pylint: disable=unused-argument

# pylint: disable=too-many-locals,too-many-arguments


@click.command()
@click.pass_context
@click.argument("session_id")
@click.argument("set_id")
@click.option(
    "--oai-pmh-url",
    default="https://clarino.uib.no/oai",
    help="URL of the OAI-PMH API from which data is retrieved",
)
@click.option(
    "--api-url",
    default="https://clarino.uib.no/comedi",
    help="URL of the API for modifying records. Comedi endpoints are assumed",
)
@click.option(
    "--uhel-distribution-rights-holder-for",
    type=click.Path(exists=True),
    help=(
        "Add UHEL as distribution rights holder for a hard-coded list of "
        "corpora that are really published by LBF."
    ),
)
@click.option(
    "--finclarin-to-organization",
    is_flag=True,
    help=(
        'If a person with surname "FIN-CLARIN" is found, move the person into an '
        "organization (if possible due to role limits)."
    ),
)
@click.option(
    "--language-bank-to-organization",
    is_flag=True,
    help=(
        'If a person with surname "The Language Bank of Finland" is found, '
        "move the person into an organization (if possible due to role limits)."
    ),
)
@click.option(
    "--add-affiliations-from",
    type=click.Path(exists=True),
    help=(
        "Path to json file specifying persons and affiliations they should be given if "
        "affiliation is not already present. See conf/example_affiliations.json for "
        "template."
    ),
)
@click.option(
    "--add-creators-from",
    type=click.Path(exists=True),
    help=(
        "Path to json file specifying persons/organizations to be added as resource"
        "creator. See conf/example_creators.json for template."
    ),
)
@click.option(
    "--save-originals-to",
    type=click.Path(
        file_okay=False, dir_okay=True, exists=True, path_type=pathlib.Path
    ),
    help="Save original XML records as files in the given directory",
)
@click.option(
    "--live-update/--dry-run",
    default=False,
    help=(
        "Choose whether to upload changes directly to production or just show the "
        "diff. Defaults to dry run."
    ),
)
@click.option("-v", "--verbose", is_flag=True, help="Print summary of modifications")
@click.option(
    "-vv",
    "--vverbose",
    is_flag=True,
    help="Print summary of modifications and list non-modified records",
)
def update_metadata(
    ctx,
    session_id,
    set_id,
    oai_pmh_url,
    api_url,
    uhel_distribution_rights_holder_for,
    finclarin_to_organization,
    language_bank_to_organization,
    add_affiliations_from,
    add_creators_from,
    live_update,
    save_originals_to,
    verbose,
    vverbose,
):
    """
    Edit all records using the specified modifications.
    """

    modifiers = selected_modifiers(ctx)

    total_records = 0
    modified_records = 0
    uploaded_records = 0
    failed_records = 0

    for cmdi_record in cmdi_records(oai_pmh_url, set_id):
        original_record_string = lxml.etree.tostring(
            cmdi_record, pretty_print=True, encoding=str
        )
        total_records += 1
        pid = cmdi_record.xpath(
            "oai:metadata/cmd:CMD/cmd:Header/cmd:MdSelfLink/text()",
            namespaces={
                "cmd": "http://www.clarin.eu/cmd/",
                "oai": "http://www.openarchives.org/OAI/2.0/",
            },
        )[0]
        pid = pid.strip()

        modified = False
        for modifier in modifiers:
            result = modifier.modify(cmdi_record)
            modified = result or modified

        if modified:
            modified_records += 1

            if save_originals_to:
                with open(
                    save_originals_to / f"{pid}.xml", "w", encoding="utf-8"
                ) as original_record_file:
                    original_record_file.write(original_record_string)

            if verbose or vverbose:
                modified_record_string = lxml.etree.tostring(
                    cmdi_record, pretty_print=True, encoding=str
                )

                diff_str = xml_string_diff(
                    original_record_string, modified_record_string
                )

                click.echo(f"Diff for {pid}:")
                click.echo(diff_str)
                click.echo()
        elif vverbose:
            click.echo(f"No changes made for {pid}")

        if modified and live_update:
            try:
                replace_record(api_url, pid, session_id, cmdi_record)
            except UploadError as err:
                click.echo(
                    f"COMEDI upload failed for record {pid}: {str(err)}",
                    err=True,
                )
                failed_records += 1
            else:
                click.echo(f"Successfully uploaded {pid}")
                uploaded_records += 1

    print(
        f"{total_records} processed, {modified_records} modified, out of "
        f"which {uploaded_records} uploaded and {failed_records} failures."
    )


if __name__ == "__main__":
    # pylint does not understand click wrappers
    # pylint: disable=no-value-for-parameter
    update_metadata()
