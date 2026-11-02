"""
Struttura dati di un certificato e modelli predefiniti (vuoto / esempio).

Struttura (dict):
{
  "header": {
      "id_certificate": "", "line": "", "dn": "", "sdr": "", "date": "",
      "article": "", "ref_standard": "", "lot1": "", "lot2": "",
      "production_batch": "", "notes": ""
  },
  "sections": [
      {"rows": [
          {"desc": "", "conf_label": "Conformity", "conf_value": "Pos",
           "columns": [{"label": "Val1", "value": "0,00"}, ...]}
      ]}
  ],
  "footer": {
      "location": "", "date": "", "notes": "",
      "prepared_by": "", "approved_by": ""
  }
}
"""
from .config import get_config


def certificato_vuoto():
    cfg = get_config()
    return {
        "header": {
            "id_certificate": "",
            "line": "",
            "dn": "",
            "sdr": "",
            "date": "",
            "article": "",
            "ref_standard": "",
            "lot1": "",
            "lot2": "",
            "production_batch": "",
            "notes": "",
        },
        "sections": [
            {
                "rows": [
                    {
                        "desc": "Descrizione della prova...",
                        "conf_label": "Conformity",
                        "conf_value": "Pos",
                        "columns": [{"label": "Val1", "value": "0,00"}],
                    }
                ]
            }
        ],
        "footer": {
            "location": "",
            "date": "",
            "notes": "",
            "prepared_by": cfg.preparato_da,
            "approved_by": cfg.approvato_da,
        },
    }


def certificato_esempio():
    cfg = get_config()
    return {
        "header": {
            "id_certificate": "51726",
            "line": "6",
            "dn": "125",
            "sdr": "17",
            "date": "01/11/2025",
            "article": "AHNN01250010B13.40 - PE100 NOIR NF PN10 D.125X7,4MM M.13,40",
            "ref_standard": "NF 114 - GR4 - PE100  e > 5 mm - APPLICAZIONI INDUSTRIALI, ACQUA NON POTABILE E FOGNA",
            "lot1": "LYONDELL BASELL - H10 - HOSTALEN CRP100 BLACK - Lotto: H10 - EK0245T21",
            "lot2": "",
            "production_batch": "OP251856",
            "notes": "",
        },
        "sections": [
            {"rows": [
                {"desc": "Oxidation stability - Oxidation stability at 210°C according to ISO 11357 and par 2.1.2 NF 114 - t ≥ 20 minutes",
                 "conf_label": "Conformity", "conf_value": "Pos",
                 "columns": [{"label": "OIT MP", "value": "50,00"}, {"label": "Int Tubo", "value": "44,00"},
                             {"label": "Mid Tubo", "value": "46,00"}, {"label": "Ext Tubo", "value": "47,00"}]},
                {"desc": "Dispersion of carbon black - ISO 18553 and par 2.1.2 NF 114 - ≤ 3",
                 "conf_label": "Conformity", "conf_value": "Pos",
                 "columns": [{"label": "Val1", "value": "1,80"}]},
                {"desc": "Raw Material: Fluidity Index - Melt flow according to NF EN ISO 1133 - Compliance with the value declared by the manufacturer",
                 "conf_label": "Conformity", "conf_value": "Pos",
                 "columns": [{"label": "Val1", "value": "0,23"}]},
                {"desc": "Hot Shrinkage - Hot shrinkage according to NF EN ISO 2505 and par 2.1.2 NF 114 - Shrinkage ≤ 3% and preserved appearance",
                 "conf_label": "Conformity", "conf_value": "Pos",
                 "columns": [{"label": "Val1", "value": "1,20"}]},
                {"desc": "Fluidity index - Melt flow according to NF EN ISO 1133 - Deviation ±10% from the value recorded on the raw material",
                 "conf_label": "Conformity", "conf_value": "Pos",
                 "columns": [{"label": "MFI MP", "value": "0,23"}, {"label": "MFI Tubo", "value": "0,23"},
                             {"label": "Diff%", "value": "-0,01"}]},
            ]},
            {"rows": [
                {"desc": "Dimensional diameter - Diameter meter - Value between diameter Min and diameter Max",
                 "conf_label": "Conformity", "conf_value": "Pos",
                 "columns": [{"label": "Min", "value": "125,00"}, {"label": "Max", "value": "125,80"},
                             {"label": "Val1", "value": "125,15"}, {"label": "Val2", "value": "125,37"},
                             {"label": "Val3", "value": "125,29"}, {"label": "Media", "value": "125,27"}]},
                {"desc": "Dimensional thickness - Micrometer - Value between Min thickness and Max thickness",
                 "conf_label": "Conformity", "conf_value": "Pos",
                 "columns": [{"label": "Min", "value": "7,40"}, {"label": "Max", "value": "8,30"},
                             {"label": "Val1", "value": "7,80"}, {"label": "Val2", "value": "7,66"},
                             {"label": "Val3", "value": "7,49"}, {"label": "Media", "value": "7,65"}]},
                {"desc": "Dimensional Ovalization - Caliber - ≤ Max Ovalization allowed",
                 "conf_label": "Conformity", "conf_value": "Pos",
                 "columns": [{"label": "Min", "value": "0,00"}, {"label": "Max", "value": "2,50"},
                             {"label": "Val1", "value": "1,47"}, {"label": "Val2", "value": "1,30"},
                             {"label": "Val3", "value": "1,33"}, {"label": "Media", "value": "1,37"}]},
            ]},
            {"rows": [
                {"desc": "Appearance: Marking - Visual - Par. 5.1 NF EN 12201-2",
                 "conf_label": "Conformity", "conf_value": "Pos", "columns": []},
                {"desc": "Appearance: Inner and outer surface - Visual - Smooth, free from irregularities",
                 "conf_label": "Conformity", "conf_value": "Pos", "columns": []},
                {"desc": "Appearance: Section - Visual - Bubble-free compact",
                 "conf_label": "Conformity", "conf_value": "Pos", "columns": []},
            ]},
            {"rows": [
                {"desc": "Resistance to slow crack propagation for thicknesses > 5 mm - Slow propagation resistance test according to NF EN ISO 13479 - ≥ 500 h - 80° C",
                 "conf_label": "Conformity", "conf_value": "Pos",
                 "columns": [{"label": "Val1", "value": "510,00"}]},
            ]},
            {"rows": [
                {"desc": "Traction - Yield strength - Yield test according to NF EN ISO 6259-1 and ISO 6259-3 and par 2.1.2 NF 114 - ≥ 19 Mpa",
                 "conf_label": "Conformity", "conf_value": "Pos",
                 "columns": [{"label": "Val1", "value": "22,60"}]},
                {"desc": "Traction - Elongation at break - Elongation test at break according to NF EN ISO 6259-1 and ISO 6259-3 and par 2.1.2 NF 114 - ≥ 500%",
                 "conf_label": "Conformity", "conf_value": "Pos",
                 "columns": [{"label": "Val1", "value": "610,80"}]},
            ]},
            {"rows": [
                {"desc": "Resistance to hydraulic pressure at 80°, 5.0 Mpa per 1000 hours - Hydraulic pressure resistance test according to NF EN ISO 1167-1 and NF EN ISO 1167-2 and par. 2.1.2 - ≥ 1000 hours",
                 "conf_label": "Conformity", "conf_value": "Pos",
                 "columns": [{"label": "Val1", "value": "1010,00"}]},
            ]},
        ],
        "footer": {
            "location": "Villadose",
            "date": "05/06/2026",
            "notes": "",
            "prepared_by": cfg.preparato_da or "Marcu Loris",
            "approved_by": cfg.approvato_da or "Massimo Buzzoni",
        },
    }
