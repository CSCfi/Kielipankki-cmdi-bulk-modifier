import click
import difflib
import json
import lxml
from sickle import Sickle

from modifiers.lb_modifiers import (
    AddOrganizationForPersonModifier,
    FinclarinPersonToOrganizationModifier,
    LanguageBankPersonToOrganizationModifier,
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

        affiliation_filename = "conf/affiliations.json"
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

    if click_context.params["finclarin_to_organization"]:
        modifiers.append(FinclarinPersonToOrganizationModifier())

    if click_context.params["language_bank_to_organization"]:
        modifiers.append(LanguageBankPersonToOrganizationModifier())

    return modifiers


def replace_record(pid, session_id, record):
    """
    Delete old record and reupload with updated data.
    """
    raise UploadError("Not implemented yet")


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
    "--upload-url",
    default="https://clarino.uib.no/comedi/upload",
    help="URL of the upload API for modified records",
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
    "--dry-run",
    is_flag=True,
    help="Output a summary of actions but make no changes to the repository",
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
    upload_url,
    finclarin_to_organization,
    language_bank_to_organization,
    add_affiliations_from,
    dry_run,
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

        modified = False
        for modifier in modifiers:
            result = modifier.modify(cmdi_record)
            modified = result or modified

        if modified:
            modified_records += 1

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

        if modified and not dry_run:
            try:
                replace_record(pid, session_id, cmdi_record)
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
