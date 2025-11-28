"""
Country code utilities and data
"""
from typing import Dict, Optional, Set

# ISO 3166-1 alpha-2 and alpha-3 country codes with names
# Source: https://www.iban.com/country-codes
COUNTRIES = {
    # A
    "AF": {"name": "Afghanistan", "alpha3": "AFG"},
    "AX": {"name": "Åland Islands", "alpha3": "ALA"},
    "AL": {"name": "Albania", "alpha3": "ALB"},
    "DZ": {"name": "Algeria", "alpha3": "DZA"},
    "AS": {"name": "American Samoa", "alpha3": "ASM"},
    "AD": {"name": "Andorra", "alpha3": "AND"},
    "AO": {"name": "Angola", "alpha3": "AGO"},
    "AI": {"name": "Anguilla", "alpha3": "AIA"},
    "AQ": {"name": "Antarctica", "alpha3": "ATA"},
    "AG": {"name": "Antigua and Barbuda", "alpha3": "ATG"},
    "AR": {"name": "Argentina", "alpha3": "ARG"},
    "AM": {"name": "Armenia", "alpha3": "ARM"},
    "AW": {"name": "Aruba", "alpha3": "ABW"},
    "AU": {"name": "Australia", "alpha3": "AUS"},
    "AT": {"name": "Austria", "alpha3": "AUT"},
    "AZ": {"name": "Azerbaijan", "alpha3": "AZE"},
    # B
    "BS": {"name": "Bahamas", "alpha3": "BHS"},
    "BH": {"name": "Bahrain", "alpha3": "BHR"},
    "BD": {"name": "Bangladesh", "alpha3": "BGD"},
    "BB": {"name": "Barbados", "alpha3": "BRB"},
    "BY": {"name": "Belarus", "alpha3": "BLR"},
    "BE": {"name": "Belgium", "alpha3": "BEL"},
    "BZ": {"name": "Belize", "alpha3": "BLZ"},
    "BJ": {"name": "Benin", "alpha3": "BEN"},
    "BM": {"name": "Bermuda", "alpha3": "BMU"},
    "BT": {"name": "Bhutan", "alpha3": "BTN"},
    "BO": {"name": "Bolivia (Plurinational State of)", "alpha3": "BOL"},
    "BQ": {"name": "Bonaire, Sint Eustatius and Saba", "alpha3": "BES"},
    "BA": {"name": "Bosnia and Herzegovina", "alpha3": "BIH"},
    "BW": {"name": "Botswana", "alpha3": "BWA"},
    "BV": {"name": "Bouvet Island", "alpha3": "BVT"},
    "BR": {"name": "Brazil", "alpha3": "BRA"},
    "IO": {"name": "British Indian Ocean Territory", "alpha3": "IOT"},
    "BN": {"name": "Brunei Darussalam", "alpha3": "BRN"},
    "BG": {"name": "Bulgaria", "alpha3": "BGR"},
    "BF": {"name": "Burkina Faso", "alpha3": "BFA"},
    "BI": {"name": "Burundi", "alpha3": "BDI"},
    # C
    "CV": {"name": "Cabo Verde", "alpha3": "CPV"},
    "KH": {"name": "Cambodia", "alpha3": "KHM"},
    "CM": {"name": "Cameroon", "alpha3": "CMR"},
    "CA": {"name": "Canada", "alpha3": "CAN"},
    "KY": {"name": "Cayman Islands", "alpha3": "CYM"},
    "CF": {"name": "Central African Republic", "alpha3": "CAF"},
    "TD": {"name": "Chad", "alpha3": "TCD"},
    "CL": {"name": "Chile", "alpha3": "CHL"},
    "CN": {"name": "China", "alpha3": "CHN"},
    "CX": {"name": "Christmas Island", "alpha3": "CXR"},
    "CC": {"name": "Cocos (Keeling) Islands", "alpha3": "CCK"},
    "CO": {"name": "Colombia", "alpha3": "COL"},
    "KM": {"name": "Comoros", "alpha3": "COM"},
    "CG": {"name": "Congo", "alpha3": "COG"},
    "CD": {"name": "Congo, Democratic Republic of the", "alpha3": "COD"},
    "CK": {"name": "Cook Islands", "alpha3": "COK"},
    "CR": {"name": "Costa Rica", "alpha3": "CRI"},
    "CI": {"name": "Côte d'Ivoire", "alpha3": "CIV"},
    "HR": {"name": "Croatia", "alpha3": "HRV"},
    "CU": {"name": "Cuba", "alpha3": "CUB"},
    "CW": {"name": "Curaçao", "alpha3": "CUW"},
    "CY": {"name": "Cyprus", "alpha3": "CYP"},
    "CZ": {"name": "Czechia", "alpha3": "CZE"},
    # D
    "DK": {"name": "Denmark", "alpha3": "DNK"},
    "DJ": {"name": "Djibouti", "alpha3": "DJI"},
    "DM": {"name": "Dominica", "alpha3": "DMA"},
    "DO": {"name": "Dominican Republic", "alpha3": "DOM"},
    # E
    "EC": {"name": "Ecuador", "alpha3": "ECU"},
    "EG": {"name": "Egypt", "alpha3": "EGY"},
    "SV": {"name": "El Salvador", "alpha3": "SLV"},
    "GQ": {"name": "Equatorial Guinea", "alpha3": "GNQ"},
    "ER": {"name": "Eritrea", "alpha3": "ERI"},
    "EE": {"name": "Estonia", "alpha3": "EST"},
    "SZ": {"name": "Eswatini", "alpha3": "SWZ"},
    "ET": {"name": "Ethiopia", "alpha3": "ETH"},
    # F
    "FK": {"name": "Falkland Islands (Malvinas)", "alpha3": "FLK"},
    "FO": {"name": "Faroe Islands", "alpha3": "FRO"},
    "FJ": {"name": "Fiji", "alpha3": "FJI"},
    "FI": {"name": "Finland", "alpha3": "FIN"},
    "FR": {"name": "France", "alpha3": "FRA"},
    "GF": {"name": "French Guiana", "alpha3": "GUF"},
    "PF": {"name": "French Polynesia", "alpha3": "PYF"},
    "TF": {"name": "French Southern Territories", "alpha3": "ATF"},
    # G
    "GA": {"name": "Gabon", "alpha3": "GAB"},
    "GM": {"name": "Gambia", "alpha3": "GMB"},
    "GE": {"name": "Georgia", "alpha3": "GEO"},
    "DE": {"name": "Germany", "alpha3": "DEU"},
    "GH": {"name": "Ghana", "alpha3": "GHA"},
    "GI": {"name": "Gibraltar", "alpha3": "GIB"},
    "GR": {"name": "Greece", "alpha3": "GRC"},
    "GL": {"name": "Greenland", "alpha3": "GRL"},
    "GD": {"name": "Grenada", "alpha3": "GRD"},
    "GP": {"name": "Guadeloupe", "alpha3": "GLP"},
    "GU": {"name": "Guam", "alpha3": "GUM"},
    "GT": {"name": "Guatemala", "alpha3": "GTM"},
    "GG": {"name": "Guernsey", "alpha3": "GGY"},
    "GN": {"name": "Guinea", "alpha3": "GIN"},
    "GW": {"name": "Guinea-Bissau", "alpha3": "GNB"},
    "GY": {"name": "Guyana", "alpha3": "GUY"},
    # H
    "HT": {"name": "Haiti", "alpha3": "HTI"},
    "HM": {"name": "Heard Island and McDonald Islands", "alpha3": "HMD"},
    "VA": {"name": "Holy See", "alpha3": "VAT"},
    "HN": {"name": "Honduras", "alpha3": "HND"},
    "HK": {"name": "Hong Kong", "alpha3": "HKG"},
    "HU": {"name": "Hungary", "alpha3": "HUN"},
    # I
    "IS": {"name": "Iceland", "alpha3": "ISL"},
    "IN": {"name": "India", "alpha3": "IND"},
    "ID": {"name": "Indonesia", "alpha3": "IDN"},
    "IR": {"name": "Iran (Islamic Republic of)", "alpha3": "IRN"},
    "IQ": {"name": "Iraq", "alpha3": "IRQ"},
    "IE": {"name": "Ireland", "alpha3": "IRL"},
    "IM": {"name": "Isle of Man", "alpha3": "IMN"},
    "IL": {"name": "Israel", "alpha3": "ISR"},
    "IT": {"name": "Italy", "alpha3": "ITA"},
    # J
    "JM": {"name": "Jamaica", "alpha3": "JAM"},
    "JP": {"name": "Japan", "alpha3": "JPN"},
    "JE": {"name": "Jersey", "alpha3": "JEY"},
    "JO": {"name": "Jordan", "alpha3": "JOR"},
    # K
    "KZ": {"name": "Kazakhstan", "alpha3": "KAZ"},
    "KE": {"name": "Kenya", "alpha3": "KEN"},
    "KI": {"name": "Kiribati", "alpha3": "KIR"},
    "KP": {"name": "Korea (Democratic People's Republic of)", "alpha3": "PRK"},
    "KR": {"name": "Korea, Republic of", "alpha3": "KOR"},
    "KW": {"name": "Kuwait", "alpha3": "KWT"},
    "KG": {"name": "Kyrgyzstan", "alpha3": "KGZ"},
    # L
    "LA": {"name": "Lao People's Democratic Republic", "alpha3": "LAO"},
    "LV": {"name": "Latvia", "alpha3": "LVA"},
    "LB": {"name": "Lebanon", "alpha3": "LBN"},
    "LS": {"name": "Lesotho", "alpha3": "LSO"},
    "LR": {"name": "Liberia", "alpha3": "LBR"},
    "LY": {"name": "Libya", "alpha3": "LBY"},
    "LI": {"name": "Liechtenstein", "alpha3": "LIE"},
    "LT": {"name": "Lithuania", "alpha3": "LTU"},
    "LU": {"name": "Luxembourg", "alpha3": "LUX"},
    # M
    "MO": {"name": "Macao", "alpha3": "MAC"},
    "MG": {"name": "Madagascar", "alpha3": "MDG"},
    "MW": {"name": "Malawi", "alpha3": "MWI"},
    "MY": {"name": "Malaysia", "alpha3": "MYS"},
    "MV": {"name": "Maldives", "alpha3": "MDV"},
    "ML": {"name": "Mali", "alpha3": "MLI"},
    "MT": {"name": "Malta", "alpha3": "MLT"},
    "MH": {"name": "Marshall Islands", "alpha3": "MHL"},
    "MQ": {"name": "Martinique", "alpha3": "MTQ"},
    "MR": {"name": "Mauritania", "alpha3": "MRT"},
    "MU": {"name": "Mauritius", "alpha3": "MUS"},
    "YT": {"name": "Mayotte", "alpha3": "MYT"},
    "MX": {"name": "Mexico", "alpha3": "MEX"},
    "FM": {"name": "Micronesia (Federated States of)", "alpha3": "FSM"},
    "MD": {"name": "Moldova, Republic of", "alpha3": "MDA"},
    "MC": {"name": "Monaco", "alpha3": "MCO"},
    "MN": {"name": "Mongolia", "alpha3": "MNG"},
    "ME": {"name": "Montenegro", "alpha3": "MNE"},
    "MS": {"name": "Montserrat", "alpha3": "MSR"},
    "MA": {"name": "Morocco", "alpha3": "MAR"},
    "MZ": {"name": "Mozambique", "alpha3": "MOZ"},
    "MM": {"name": "Myanmar", "alpha3": "MMR"},
    # N
    "NA": {"name": "Namibia", "alpha3": "NAM"},
    "NR": {"name": "Nauru", "alpha3": "NRU"},
    "NP": {"name": "Nepal", "alpha3": "NPL"},
    "NL": {"name": "Netherlands", "alpha3": "NLD"},
    "NC": {"name": "New Caledonia", "alpha3": "NCL"},
    "NZ": {"name": "New Zealand", "alpha3": "NZL"},
    "NI": {"name": "Nicaragua", "alpha3": "NIC"},
    "NE": {"name": "Niger", "alpha3": "NER"},
    "NG": {"name": "Nigeria", "alpha3": "NGA"},
    "NU": {"name": "Niue", "alpha3": "NIU"},
    "NF": {"name": "Norfolk Island", "alpha3": "NFK"},
    "MK": {"name": "North Macedonia", "alpha3": "MKD"},
    "MP": {"name": "Northern Mariana Islands", "alpha3": "MNP"},
    "NO": {"name": "Norway", "alpha3": "NOR"},
    # O
    "OM": {"name": "Oman", "alpha3": "OMN"},
    # P
    "PK": {"name": "Pakistan", "alpha3": "PAK"},
    "PW": {"name": "Palau", "alpha3": "PLW"},
    "PS": {"name": "Palestine, State of", "alpha3": "PSE"},
    "PA": {"name": "Panama", "alpha3": "PAN"},
    "PG": {"name": "Papua New Guinea", "alpha3": "PNG"},
    "PY": {"name": "Paraguay", "alpha3": "PRY"},
    "PE": {"name": "Peru", "alpha3": "PER"},
    "PH": {"name": "Philippines", "alpha3": "PHL"},
    "PN": {"name": "Pitcairn", "alpha3": "PCN"},
    "PL": {"name": "Poland", "alpha3": "POL"},
    "PT": {"name": "Portugal", "alpha3": "PRT"},
    "PR": {"name": "Puerto Rico", "alpha3": "PRI"},
    # Q
    "QA": {"name": "Qatar", "alpha3": "QAT"},
    # R
    "RE": {"name": "Réunion", "alpha3": "REU"},
    "RO": {"name": "Romania", "alpha3": "ROU"},
    "RU": {"name": "Russian Federation", "alpha3": "RUS"},
    "RW": {"name": "Rwanda", "alpha3": "RWA"},
    # S
    "BL": {"name": "Saint Barthélemy", "alpha3": "BLM"},
    "SH": {"name": "Saint Helena, Ascension and Tristan da Cunha", "alpha3": "SHN"},
    "KN": {"name": "Saint Kitts and Nevis", "alpha3": "KNA"},
    "LC": {"name": "Saint Lucia", "alpha3": "LCA"},
    "MF": {"name": "Saint Martin (French part)", "alpha3": "MAF"},
    "PM": {"name": "Saint Pierre and Miquelon", "alpha3": "SPM"},
    "VC": {"name": "Saint Vincent and the Grenadines", "alpha3": "VCT"},
    "WS": {"name": "Samoa", "alpha3": "WSM"},
    "SM": {"name": "San Marino", "alpha3": "SMR"},
    "ST": {"name": "Sao Tome and Principe", "alpha3": "STP"},
    "SA": {"name": "Saudi Arabia", "alpha3": "SAU"},
    "SN": {"name": "Senegal", "alpha3": "SEN"},
    "RS": {"name": "Serbia", "alpha3": "SRB"},
    "SC": {"name": "Seychelles", "alpha3": "SYC"},
    "SL": {"name": "Sierra Leone", "alpha3": "SLE"},
    "SG": {"name": "Singapore", "alpha3": "SGP"},
    "SX": {"name": "Sint Maarten (Dutch part)", "alpha3": "SXM"},
    "SK": {"name": "Slovakia", "alpha3": "SVK"},
    "SI": {"name": "Slovenia", "alpha3": "SVN"},
    "SB": {"name": "Solomon Islands", "alpha3": "SLB"},
    "SO": {"name": "Somalia", "alpha3": "SOM"},
    "ZA": {"name": "South Africa", "alpha3": "ZAF"},
    "GS": {"name": "South Georgia and the South Sandwich Islands", "alpha3": "SGS"},
    "SS": {"name": "South Sudan", "alpha3": "SSD"},
    "ES": {"name": "Spain", "alpha3": "ESP"},
    "LK": {"name": "Sri Lanka", "alpha3": "LKA"},
    "SD": {"name": "Sudan", "alpha3": "SDN"},
    "SR": {"name": "Suriname", "alpha3": "SUR"},
    "SJ": {"name": "Svalbard and Jan Mayen", "alpha3": "SJM"},
    "SE": {"name": "Sweden", "alpha3": "SWE"},
    "CH": {"name": "Switzerland", "alpha3": "CHE"},
    "SY": {"name": "Syrian Arab Republic", "alpha3": "SYR"},
    # T
    "TW": {"name": "Taiwan, Province of China", "alpha3": "TWN"},
    "TJ": {"name": "Tajikistan", "alpha3": "TJK"},
    "TZ": {"name": "Tanzania, United Republic of", "alpha3": "TZA"},
    "TH": {"name": "Thailand", "alpha3": "THA"},
    "TL": {"name": "Timor-Leste", "alpha3": "TLS"},
    "TG": {"name": "Togo", "alpha3": "TGO"},
    "TK": {"name": "Tokelau", "alpha3": "TKL"},
    "TO": {"name": "Tonga", "alpha3": "TON"},
    "TT": {"name": "Trinidad and Tobago", "alpha3": "TTO"},
    "TN": {"name": "Tunisia", "alpha3": "TUN"},
    "TR": {"name": "Türkiye", "alpha3": "TUR"},
    "TM": {"name": "Turkmenistan", "alpha3": "TKM"},
    "TC": {"name": "Turks and Caicos Islands", "alpha3": "TCA"},
    "TV": {"name": "Tuvalu", "alpha3": "TUV"},
    # U
    "UG": {"name": "Uganda", "alpha3": "UGA"},
    "UA": {"name": "Ukraine", "alpha3": "UKR"},
    "AE": {"name": "United Arab Emirates", "alpha3": "ARE"},
    "GB": {"name": "United Kingdom of Great Britain and Northern Ireland", "alpha3": "GBR"},
    "US": {"name": "United States of America", "alpha3": "USA"},
    "UM": {"name": "United States Minor Outlying Islands", "alpha3": "UMI"},
    "UY": {"name": "Uruguay", "alpha3": "URY"},
    "UZ": {"name": "Uzbekistan", "alpha3": "UZB"},
    # V
    "VU": {"name": "Vanuatu", "alpha3": "VUT"},
    "VE": {"name": "Venezuela (Bolivarian Republic of)", "alpha3": "VEN"},
    "VN": {"name": "Viet Nam", "alpha3": "VNM"},
    "VG": {"name": "Virgin Islands (British)", "alpha3": "VGB"},
    "VI": {"name": "Virgin Islands (U.S.)", "alpha3": "VIR"},
    # W
    "WF": {"name": "Wallis and Futuna", "alpha3": "WLF"},
    "EH": {"name": "Western Sahara", "alpha3": "ESH"},
    # Y
    "YE": {"name": "Yemen", "alpha3": "YEM"},
    # Z
    "ZM": {"name": "Zambia", "alpha3": "ZMB"},
    "ZW": {"name": "Zimbabwe", "alpha3": "ZWE"},
}

# Create a set of all valid alpha-2 and alpha-3 codes
VALID_COUNTRY_CODES: Set[str] = set(COUNTRIES.keys()) | {
    info["alpha3"] for info in COUNTRIES.values()
}

def is_valid_country_code(code: str) -> bool:
    """Check if a string is a valid ISO 3166-1 alpha-2 or alpha-3 country code."""
    if not code or not isinstance(code, str):
        return False
    return code.upper() in VALID_COUNTRY_CODES

def get_country_info(code: str) -> Optional[Dict[str, str]]:
    """
    Get country information by alpha-2 or alpha-3 code.
    
    Args:
        code: ISO 3166-1 alpha-2 or alpha-3 country code
        
    Returns:
        Dict with country info (name, alpha2, alpha3) or None if not found
    """
    if not code or not isinstance(code, str):
        return None
        
    code_upper = code.upper()
    
    # First try direct lookup (alpha-2)
    if code_upper in COUNTRIES:
        info = COUNTRIES[code_upper].copy()
        info["alpha2"] = code_upper
        return info
    
    # Then search for alpha-3
    for alpha2, info in COUNTRIES.items():
        if info["alpha3"] == code_upper:
            result = info.copy()
            result["alpha2"] = alpha2
            return result
    
    return None
