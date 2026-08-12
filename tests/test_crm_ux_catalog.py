from __future__ import annotations
import unittest
from services.crm_ux_catalog import CRM_UX_CATALOG

class CrmUxCatalogTests(unittest.TestCase):
    def test_catalog_covers_main_operational_surfaces(self) -> None:
        titles = {item[0] for item in CRM_UX_CATALOG}
        self.assertTrue({"Funil", "Caso em foco", "Documentos", "Automações", "Contratos", "Indicadores"}.issubset(titles))
        self.assertTrue(all(len(item) == 3 and all(part for part in item) for item in CRM_UX_CATALOG))

if __name__ == "__main__":
    unittest.main()
