"""
Modifiers used with FIN-CLARIN data.
"""

import lxml
import sys

from modifiers.base import BaseModifier


class AddCreatorFromJsonModifier(BaseModifier):
    """
    Modifier that adds resource creator information based on an input JSON file.

    The expected structure for the JSON file is a dict containing creator information
    dicts identified by their URN as the key. Each creatir information dict represents
    one CMDI resource. Only fields "tekija" and "author" are required for this
    modifier. If the author is an organization, its information should be in curly
    brackets. If there are more than one author, each person must be separated by a
    semicolon. Mixing persons and organizations is not supported.

    Creator parsing is a somewhat fuzzy task, so information about persons/organizations
    that look somehow "off" and thus are not inserted is produced. This is printed to
    stderr to make it easy to separate these from the diffs of the successfully edited
    records.

    Example dict:
    {
      "urn:nbn:fi:lb-2016042710": {
        "lyhenne": "acquis-ftb3",
        "tekija": "{Euroopan komission yhteinen tutkimuskeskus (JRC)}",
        "author": "{European Commission - Joint Research Centre (JRC)}"
      },
      "urn:nbn:fi:lb-000000000": {
        "lyhenne": "example-corpus",
        "tekija": "Tiina Tutkija; Kiira Korpuksentekijä",
        "author": "Tiina Tutkija; Kiira Korpuksentekijä"
      },
      "urn:nbn:fi:lb-2019121804": {
        "lyhenne": "agricola-v1-1-korp",
        "tekija": "",
        "author": ""
      }
    }
    """

    def __init__(self, creator_dicts, *args, **kwargs):
        """
        :param creator_dicts: Source of author information. See class docstring.
        :type creator_dicts: list of dicts
        """
        self.creator_dicts = creator_dicts
        super().__init__(*args, **kwargs)

    def _matching_author_dict(self, cmdi_record):
        """
        Return the author dict matching the given record.

        Matching is done based on URN. If a matching dict is not found, returns None.
        """

        identifier = self.elements_matching_xpath(
            cmdi_record, "oai:metadata/cmd:CMD/cmd:Header/cmd:MdSelfLink/text()"
        )[0]
        return self.creator_dicts.get(identifier, None)

    def _organization_element(self, cmdi_record, author_en, author_fi):
        """
        Return a ready-to-be-inserted lxml Element for creator info for an organization,
        or None if one cannot be constructed.

        All organizations are assumed to be contained within curly braces: if opening
        curly brace is not found, the organization is simply skipped.

        We can only return an organization element when we find an exact match for the
        organization name exists in the pre-existing metadata, as otherwise we wouldn't
        be able to populate the communicationInfo element required in our metadata
        profile.
        """
        if (not author_en or not author_en[0] == "{") and (
            not author_fi or not author_fi[0] == "{"
        ):
            return None

        author_en = author_en.strip("{}")
        author_fi = author_fi.strip("{}")

        condition = (
            f".//cmd:organizationInfo["
            f"cmd:organizationName[@xml:lang='en' and text()=\"{author_en}\"]"
            " or "
            f"cmd:organizationName[@xml:lang='fi' and text()='{author_fi}']"
            "]"
        )

        pre_existing_organization_infos = self.elements_matching_xpath(
            cmdi_record, condition
        )
        if not pre_existing_organization_infos:
            return None

        organization_element = lxml.etree.fromstring(
            """
            <resourceCreatorOrganization xmlns="http://www.clarin.eu/cmd/">
                <role>resourceCreator</role>
            </resourceCreatorOrganization>
            """
        )
        organization_element.append(
            lxml.etree.fromstring(
                lxml.etree.tostring(pre_existing_organization_infos[0])
            )
        )
        return organization_element

    def _person_element(self, cmdi_record, author_en, author_fi):
        """
        Return a ready-to-be-inserted lxml Element for creator info of a person.

        All strings that have an opening curly braces in them are assumed to represent
        an organization and are thus skipped.

        For persons, the source data should contain either one language variant of the
        name or both of them should be identical. If not, the author is not processed.
        """

        if "{" in author_en or "{" in author_fi:
            return None

        author_en = author_en.strip()
        author_fi = author_fi.strip()

        try:
            if author_en == author_fi:
                first_name, last_name = author_en.split()
            elif not author_en:
                first_name, last_name = author_fi.split()
            elif not author_fi:
                first_name, last_name = author_en.split()
            else:
                print(
                    f"Ambiguous author {author_en} / {author_fi} found", file=sys.stderr
                )
                return None
        except ValueError:
            print(
                f"Could not determine first/last name split for {author_en} / "
                f"{author_fi}",
                file=sys.stderr,
            )
            return None

        condition = (
            f".//cmd:personInfo["
            f'cmd:givenName[text()="{first_name}"]'
            " and "
            f'cmd:surname[text()="{last_name}"]'
            "]"
        )

        pre_existing_person_infos = self.elements_matching_xpath(cmdi_record, condition)
        if not pre_existing_person_infos:
            return None

        person_element = lxml.etree.fromstring(
            """
            <resourceCreatorPerson xmlns="http://www.clarin.eu/cmd/">
                <role>resourceCreator</role>
            </resourceCreatorPerson>
            """
        )
        person_element.append(
            lxml.etree.fromstring(lxml.etree.tostring(pre_existing_person_infos[0]))
        )
        return person_element

    def modify(self, cmdi_record):
        identifier = self.elements_matching_xpath(
            cmdi_record, "oai:metadata/cmd:CMD/cmd:Header/cmd:MdSelfLink/text()"
        )[0]
        author_dict = self.creator_dicts.get(identifier, None)
        if not author_dict:
            return False

        pre_existing_resource_creation_info = self.elements_matching_xpath(
            cmdi_record, ".//cmd:resourceCreationInfo"
        )
        if pre_existing_resource_creation_info:
            print(
                f"Resource creation info already available for {author_dict['lyhenne']} "
                f"/ {identifier}, skipping",
                file=sys.stderr,
            )

        authors_en = author_dict["author"].split(";")
        authors_fi = author_dict["tekija"].split(";")

        if len(authors_en) != len(authors_fi):
            print(
                "Different number of authors in Finnish and English for "
                f"{author_dict['lyhenne']}",
                file=sys.stderr,
            )
            return False

        author_infos = []
        for author_en, author_fi in zip(authors_en, authors_fi):
            if not author_en and not author_fi:
                # empty strings can be skipped right away
                continue

            organization_info = self._organization_element(
                cmdi_record, author_en, author_fi
            )
            if organization_info is not None:
                author_infos.append(organization_info)
                continue

            person_info = self._person_element(cmdi_record, author_en, author_fi)
            if person_info is not None:
                author_infos.append(person_info)
                continue

            print(
                f"Could not map author {author_fi} / {author_en} for {identifier}, "
                "skipping the record.",
                file=sys.stderr,
            )
            return False

        if not author_infos:
            print(f"No authors parsed for {author_dict['lyhenne']}", file=sys.stderr)
            return False

        resource_creation_info = lxml.etree.fromstring(
            """
            <resourceCreationInfo  xmlns="http://www.clarin.eu/cmd/">
            </resourceCreationInfo>
            """
        )

        for author_element in author_infos:
            resource_creation_info.append(author_element)

        self.elements_matching_xpath(cmdi_record, ".//cmd:resourceInfo")[0].append(
            resource_creation_info
        )
        lxml.etree.indent(cmdi_record)
        return True


class AddDistributionRightsHolderModifier(BaseModifier):
    """
    Modifier that adds a distribution rights holder to a given set of records.
    """

    def __init__(
        self, modified_identifiers, distribution_rights_holder_str, *args, **kwargs
    ):
        """
        :param modified_identifiers: Identifiers (e.g. "urn:nbn:fi:lb-123") that specify which
                                     records should be modified. Records whose identifier is not
                                     found in the list are not altered. The identifier is
                                     assumed to be found in MdSelfLink field in the
                                     header.
        :type modified_identifiers: list
        :param distribution_rights_holder_str: String representing the XML content to be inserted as
                                               publisher
        :type distribution_rights_holder_str: str
        """
        self.modified_identifiers = modified_identifiers
        self.distribution_rights_holder_str = distribution_rights_holder_str
        super().__init__(*args, **kwargs)

    def is_listed_for_modification(self, cmdi_record):
        """
        Return True if the given record should be modified.

        :param cmdi_record: The full record that is up for modifications
        :type cmdi_record: lxml.etree
        """
        identifier = self.elements_matching_xpath(
            cmdi_record, "oai:metadata/cmd:CMD/cmd:Header/cmd:MdSelfLink/text()"
        )[0]
        return identifier in self.modified_identifiers

    def modify(self, cmdi_record):
        if not self.is_listed_for_modification(cmdi_record):
            return False

        if self.elements_matching_xpath(
            cmdi_record,
            "./cmd:distributionInfo/cmd:licenceInfo/cmd:distributionRightsHolderPerson",
        ) or self.elements_matching_xpath(
            cmdi_record,
            "./cmd:distributionInfo/cmd:licenceInfo/cmd:distributionRightsHolderOrganization",
        ):
            raise ValueError("At least one distribution rightsholder already present")

        license_info_element = self.elements_matching_xpath(
            cmdi_record,
            "./oai:metadata/cmd:CMD/cmd:Components/cmd:resourceInfo/cmd:distributionInfo/cmd:licenceInfo",
        )[0]
        new_distribution_rights_holder_element = lxml.etree.fromstring(
            self.distribution_rights_holder_str
        )
        license_info_element.append(new_distribution_rights_holder_element)

        lxml.etree.indent(cmdi_record)

        return True


class UhelDistributionRightsHolderModifier(AddDistributionRightsHolderModifier):
    """
    Add UHEL as distribution rights holder for corpora published by LBF.
    """

    def __init__(self, affected_identifiers):
        distribution_rights_holder_str = """
        <distributionRightsHolderOrganization>
            <role>distributionRightsHolder</role>
            <organizationInfo>
                <organizationName xml:lang="en">University of Helsinki</organizationName>
                <organizationShortName xml:lang="en">UHEL</organizationShortName>
                <communicationInfo>
                    <email>fin-clarin@helsinki.fi</email>
                </communicationInfo>
            </organizationInfo>
        </distributionRightsHolderOrganization>
        """

        super().__init__(affected_identifiers, distribution_rights_holder_str)


class PersonToOrganizationModifier(BaseModifier):
    """
    Modifier that fixes records where an organization is reported as a person.

    NB: at the moment, the plan for contact persons and licensor persons is to keep the
    "person" as is, and just add the correct organization as affiliation for that
    "person". Thus, these are not handled by this modifier: use
    AddOrganizationForPersonModifier instead.
    """

    def __init__(self, person_surname, organization_info_str):
        self.person_surname = person_surname
        self.organization_info_str = organization_info_str
        super().__init__()

    def modify(self, cmdi_record):
        modified = False
        organization_persons = self.elements_matching_xpath(
            cmdi_record,
            f'.//cmd:personInfo[./cmd:surname[text()="{self.person_surname}"]]',
        )
        for person_element in organization_persons:
            parent = person_element.getparent()

            if parent.tag in [
                "{http://www.clarin.eu/cmd/}contactPerson",
                "{http://www.clarin.eu/cmd/}metadataCreator",
            ]:
                continue
            elif (
                parent.tag
                == "{http://www.clarin.eu/cmd/}distributionRightsHolderPerson"
            ):
                modified = True
                new_element = lxml.etree.fromstring(
                    """
                    <distributionRightsHolderOrganization xmlns="http://www.clarin.eu/cmd/">
                        <role>distributionRightsHolder</role>
                    </distributionRightsHolderOrganization>
                    """
                )
                organization_info_element = lxml.etree.fromstring(
                    self.organization_info_str
                )
                new_element.append(organization_info_element)
                grandparent = parent.getparent()
                grandparent.replace(parent, new_element)
            elif parent.tag == "{http://www.clarin.eu/cmd/}licensorPerson":
                modified = True
                new_element = lxml.etree.fromstring(
                    """
                    <licensorOrganization xmlns="http://www.clarin.eu/cmd/">
                        <role>licensor</role>
                    </licensorOrganization>
                    """
                )
                organization_info_element = lxml.etree.fromstring(
                    self.organization_info_str
                )
                new_element.append(organization_info_element)
                grandparent = parent.getparent()
                grandparent.replace(parent, new_element)
            else:
                raise ValueError(
                    f"Unexpected person element of type {parent.tag} encountered"
                )
        lxml.etree.indent(cmdi_record)
        return modified


class FinclarinPersonToOrganizationModifier(PersonToOrganizationModifier):
    """
    Modifier that fixes records where there is a person whose surname is FIN-CLARIN.
    """

    def __init__(self):
        organization_info_str = """
            <organizationInfo>
                <organizationName xml:lang="en">FIN-CLARIN</organizationName>
                <organizationShortName xml:lang="en">FIN-CLARIN</organizationShortName>
                <departmentName xml:lang="en">University of Helsinki</departmentName>
                <communicationInfo>
                    <email>fin-clarin@helsinki.fi</email>
                    <url>http://www.helsinki.fi/fin-clarin</url>
                    <address>PO Box 24 (Unioninkatu 40)</address>
                    <zipCode>00014</zipCode>
                    <city>University of Helsinki</city>
                    <country>Finland</country>
                </communicationInfo>
            </organizationInfo>
            """
        super().__init__(
            person_surname="FIN-CLARIN", organization_info_str=organization_info_str
        )


class LanguageBankPersonToOrganizationModifier(PersonToOrganizationModifier):
    """
    Modifier that fixes records where there is a person whose surname is "The Language
    Bank of Finland".
    """

    def __init__(self):
        organization_info_str = """
            <organizationInfo>
                <organizationName xml:lang="fi">CSC - Tieteen tietotekniikan keskus Oy</organizationName>
                <organizationName xml:lang="en">CSC — IT Center for Science Ltd</organizationName>
                <organizationShortName xml:lang="en">CSC</organizationShortName>
                <departmentName xml:lang="en">Kielipankki</departmentName>
                <communicationInfo>
                    <email>kielipankki@csc.fi</email>
                    <url>http://www.csc.fi/english</url>
                    <address>P.O. Box 405</address>
                    <zipCode>FI-02101</zipCode>
                    <city>Espoo</city>
                    <country>Finland</country>
                    <telephoneNumber>+358 (0)9 457 2001</telephoneNumber>
                    <faxNumber>+358 (0)9 457 2302</faxNumber>
                </communicationInfo>
            </organizationInfo>
            """
        super().__init__(
            person_surname="The Language Bank of Finland",
            organization_info_str=organization_info_str,
        )


class AddOrganizationForPersonModifier(BaseModifier):
    """
    Modifier that finds matching persons without an organization and adds it.

    Persons are matched based on name (first name and surname) and not having an
    organization yet.
    """

    def __init__(self, first_name, surname, organization_info_str):
        """
        Create a new modifier for a specific person

        :param first_name: First name of the edited person
        :type firstn_name: str
        :param surname: Surname of the edited person
        :type surname: str
        :param organization_info_str: CMDI representation of the organization
                                      (<OrganizationInfo>...</OrganizationInfo>)
        :type organization_info_str: str
        """
        self.first_name = first_name
        self.surname = surname
        self.organization_info_str = organization_info_str
        super().__init__()

    def modify(self, cmdi_record):
        modified = False
        matching_persons = self.elements_matching_xpath(
            cmdi_record,
            f".//cmd:personInfo["
            f' ./cmd:surname[text()="{self.surname}"]'
            f' and ./cmd:givenName[text()="{self.first_name}"]'
            f"]["
            f"not(child::cmd:affiliation)"
            f"]",
        )
        for person in matching_persons:
            affiliation_element = lxml.etree.fromstring(
                "<affiliation><role>affiliation</role></affiliation>"
            )
            organization_info_element = lxml.etree.fromstring(
                self.organization_info_str
            )
            affiliation_element.append(organization_info_element)
            person.append(affiliation_element)
            lxml.etree.indent(cmdi_record)

            modified = True
        return modified
