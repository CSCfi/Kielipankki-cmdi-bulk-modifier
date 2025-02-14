"""
Modifiers used with FIN-CLARIN data.
"""

import lxml

from modifiers.base import BaseModifier


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
                                     assumed to be found in "//cmd:Header/cmd:MdSelfLink/text()".
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
                    <email>firstname.surname@helsinki.fi</email>
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
