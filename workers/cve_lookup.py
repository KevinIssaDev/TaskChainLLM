import pandas as pd
import requests
from io import StringIO
from typing import List, Dict


def cve_lookup(cve_list: str) -> List[Dict]:
    """
    Looks up information for specified CVEs from CISA's known exploited vulnerabilities database.

    Args:
        cve_list (str): A comma-separated string of CVE IDs to look up.

    Returns:
        List[Dict]: A list of dictionaries containing information for the specified CVEs.

    Example Usage:
        [[WORKER: {"name": "cve_lookup", "args": {"cve_list": "CVE-2024-43573,CVE-2023-12345"}}]]
    """
    url = "https://www.cisa.gov/sites/default/files/csv/known_exploited_vulnerabilities.csv"

    response = requests.get(url)

    if response.status_code == 200:
        csv_data = StringIO(response.text)
        df = pd.read_csv(csv_data)

        cve_ids = [cve.strip() for cve in cve_list.split(',')]

        result_df = df[df['cveID'].isin(cve_ids)]
        json_result = result_df.to_json(orient='records')

        return json_result
    else:
        raise Exception("Error: Unable to download CVE data.")


worker = cve_lookup

# Example usage
# if __name__ == "__main__":
#     cve_data = cve_lookup("CVE-2024-43573")
#     print(cve_data)
