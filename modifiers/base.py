class BaseModifier:
    def __init__(self, cmdi_record, namespaces=None):
        """
        Create new modifier

        :param cmdi_record: Record to be modified
        :type cmdi_record: lxml.etree.Element
        :param namespaces: Namespaces used in the record in lxml compatible dict.
                           Defaults to CMDI and OAI namespaces used in FIN-CLARIN data.
        :type namespaces: dict
        """
        self.cmdi_record = cmdi_record
        if namespaces:
            self.namespaces = namespaces
        else:
            self.namespaces = {
                "cmd": "http://www.clarin.eu/cmd/",
                "oai": "http://www.openarchives.org/OAI/2.0/",
            }

    def modify(self):
        """
        Implementation for the specific modification(s) carried out by the modifier.

        Modifies the cmdi_record in place.

        :returns: True if modifications were carried out, otherwise False
        """
        raise NotImplementedError("Must be implemented in subclasses")

    def elements_matching_xpath(self, xpath):
        """
        Return all elements that match the given xpath.
        """
        return self.cmdi_record.xpath(xpath, namespaces=self.namespaces)