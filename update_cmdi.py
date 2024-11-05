import click
import lxml
from sickle import Sickle

from modifiers.lb_modifiers import FinclarinPersonToOrganizationModifier


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
    # TODO really parse from arguments
    return [FinclarinPersonToOrganizationModifier]


def replace_record(pid, session_id, record):
    """
    Delete old record and reupload with updated data.
    """
    raise UploadError("Not implemented yet")


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
    "--dry-run",
    is_flag=True,
    help="Output a summary of actions but make no changes to the repository",
)
def update_metadata(
    ctx,
    session_id,
    set_id,
    oai_pmh_url,
    upload_url,
    dry_run,
):
    """
    Edit all records using the specified modifications.
    """

    # TODO: remove this, it is here to make testing easier
    dry_run = True

    modifiers = selected_modifiers(ctx)

    total_records = 0
    modified_records = 0
    failed_records = 0

    for cmdi_record in cmdi_records(oai_pmh_url, set_id):
        total_records += 1
        pid = cmdi_record.xpath(
            "oai:metadata/cmd:CMD/cmd:Header/cmd:MdSelfLink/text()",
            namespaces={
                "cmd": "http://www.clarin.eu/cmd/",
                "oai": "http://www.openarchives.org/OAI/2.0/",
            },
        )[0]

        for modifier_class in modifiers:
            modifier = modifier_class(cmdi_record)

        if not dry_run:
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
                modified_records += 1

    print(
        f"{total_records} processed, "
        f"{modified_records} uploads and {failed_records} failures."
    )


if __name__ == "__main__":
    # pylint does not understand click wrappers
    # pylint: disable=no-value-for-parameter
    update_metadata()
