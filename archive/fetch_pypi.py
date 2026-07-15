import requests
import hashlib

def get_package_data(package, version):
    url = f"https://pypi.org/pypi/{package}/{version}/json"
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Error fetching {package}: {response.status_code}")
        return

    data = response.json()
    for release in data['urls']:
        if release['packagetype'] == 'sdist':
            print(f'  resource "{package}" do')
            print(f'    url "{release["url"]}"')
            print(f'    sha256 "{release["digests"]["sha256"]}"')
            print('  end\n')
            return
    print(f"No sdist found for {package}")

print("# Dependencies")
get_package_data("colorama", "0.4.6")
get_package_data("humanize", "4.9.0")
get_package_data("Send2Trash", "1.8.2")
