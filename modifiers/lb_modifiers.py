"""
Modifiers used with FIN-CLARIN data.
"""

import lxml

from modifiers.base import BaseModifier


class FinclarinPersonToOrganizationModifier(BaseModifier):
    """
    Modifier that fixes records where there is a person whose surname is FIN-CLARIN.
    """

    def modify(self, cmdi_record):
        modified = False
        finclarin_persons = self.elements_matching_xpath(
            cmdi_record,
            './/cmd:personInfo[./cmd:surname[text()="FIN-CLARIN"]]',
        )
        for person_element in finclarin_persons:
            parent = person_element.getparent()

            if parent.tag == "{http://www.clarin.eu/cmd/}contactPerson":
                # TODO
                continue
            elif parent.tag == "{http://www.clarin.eu/cmd/}licensorPerson":
                modified = True
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
                    f"Unexpected person element of type {parent.tag} encountered"
                )
        lxml.etree.indent(cmdi_record)
        return modified


class LanguageBankPersonToOrganizationModifier(BaseModifier):
    """
    Modifier that fixes records where there is a person whose surname is "The Language
    Bank of Finland".
    """

    def modify(self, cmdi_record):
        modified = False
        finclarin_persons = self.elements_matching_xpath(
            cmdi_record,
            './/cmd:personInfo[./cmd:surname[text()="The Language Bank of Finland"]]',
        )
        for person_element in finclarin_persons:
            parent = person_element.getparent()

            if parent.tag in [
                "{http://www.clarin.eu/cmd/}contactPerson",
                "{http://www.clarin.eu/cmd/}metadataCreator",
            ]:
                # TODO
                continue
            elif (
                parent.tag
                == "{http://www.clarin.eu/cmd/}distributionRightsHolderPerson"
            ):
                # TODO
                continue
            elif parent.tag == "{http://www.clarin.eu/cmd/}licensorPerson":
                modified = True
                new_element = lxml.etree.fromstring(
                    """
                    <licensorOrganization xmlns="http://www.clarin.eu/cmd/">
                        <role>licensor</role>
                        <organizationInfo>
                            <organizationName>CSC - IT Center for Science Ltd.</organizationName>
                            <departmentName>The Language Bank of Finland</departmentName>
                            <communicationInfo>
                                <email>kielipankki@csc.fi</email>
                            </communicationInfo>
                        </organizationInfo>
                    </licensorOrganization>
                    """
                )
                grandparent = parent.getparent()
                grandparent.replace(parent, new_element)
            else:
                raise ValueError(
                    f"Unexpected person element of type {parent.tag} encountered"
                )
        lxml.etree.indent(cmdi_record)
        return modified


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
        self.organization_info = lxml.etree.fromstring(organization_info_str)
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
            affiliation_element.append(self.organization_info)
            person.append(affiliation_element)
            lxml.etree.indent(cmdi_record)

            modified = True
        return modified
