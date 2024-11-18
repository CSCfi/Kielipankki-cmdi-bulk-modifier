"""
Modifiers used with FIN-CLARIN data.
"""

import lxml

from modifiers.base import BaseModifier


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
                <organizationName>FIN-CLARIN</organizationName>
                <communicationInfo>
                    <email>fin-clarin@helsinki.fi</email>
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
                <organizationName>CSC - IT Center for Science Ltd.</organizationName>
                <departmentName>The Language Bank of Finland</departmentName>
                <communicationInfo>
                    <email>kielipankki@csc.fi</email>
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

        :paran first_name: First name of the edited person
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
