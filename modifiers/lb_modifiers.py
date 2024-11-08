"""
Modifiers used with FIN-CLARIN data.
"""

import lxml

from modifiers.base import BaseModifier


class FinclarinPersonToOrganizationModifier(BaseModifier):
    """
    Modifier that fixes records where there is a person whose surname is FIN-CLARIN.
    """

    def modify(self):
        modified = False
        finclarin_persons = self.elements_matching_xpath(
            './/cmd:personInfo[./cmd:surname[text()="FIN-CLARIN"]]',
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
        lxml.etree.indent(self.cmdi_record)
        return modified
