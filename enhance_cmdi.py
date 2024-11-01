import click
import lxml
from sickle import Sickle


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


def selected_enhancers(click_context):
    """
    Return a list of enhancers the user has selected using flags.
    """
    # TODO really parse from arguments
    return [finclarin_person_enhancer]


def replace_record(pid, session_id, record):
    """
    Delete old record and reupload with updated data.
    """
    raise UploadError("Not implemented yet")


def finclarin_person_enhancer(cmdi_record):
    """
    Change FIN-CLARIN recorded as a person into an organization
    """
    modified = False
    finclarin_persons = cmdi_record.xpath(
        '//cmd:personInfo[./cmd:surname[text()="FIN-CLARIN"]]',
        namespaces={"cmd": "http://www.clarin.eu/cmd/"},
    )

    for person_element in finclarin_persons:
        modified = True
        parent = person_element.getparent()

        if parent.tag == "{http://www.clarin.eu/cmd/}contactPerson":
            # TODO
            continue
        elif parent.tag == "{http://www.clarin.eu/cmd/}licensorPerson":
            new_element = lxml.etree.fromstring(
                """
                <licensorOrganization xmlns="http://www.clarin.eu/cmd/">
                    <role>licensor</role>
                    <organizationInfo>
                        <organizationName>FIN-CLARIN</organizationName>
                        <communicationInfo>
                            <email>fin-clarin@helsinki.fi</email>
                        </communicationInfo>
                    </organizationInfo>
                </licensorOrganization>
                """
            )
            grandparent = parent.getparent()
            grandparent.replace(parent, new_element)
        else:
            raise ValueError(
                "Unexpected person element of type {parent.tag} encountered"
            )

    return modified


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
def enhance_metadata(
    ctx,
    session_id,
    set_id,
    oai_pmh_url,
    upload_url,
    dry_run,
):
    """
    Enhance all records using the specified enhancers.
    """

    # TODO: remove this, it is here to make testing easier
    dry_run = True

    enhancers = selected_enhancers(ctx)

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

        for enhancer in enhancers:
            enhancer(cmdi_record)

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
    enhance_metadata()
