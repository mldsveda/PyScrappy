def _extract_page_number(self, url):
    match = self._PAGE_NUMBER.search(url)
    if match:
        # Check if the matched group is for offset or start
        if match.group(1) and ('offset=' in url or 'start=' in url):
            # Return the current offset value
            return int(match.group(1))
        elif match.group(2):
            # Return the current page number
            return int(match.group(2))
    return None


def find_next_page_url(self, url, page_size):
    match = self._PAGE_NUMBER.search(url)
    if match:
        if match.group(1) and ('offset=' in url or 'start=' in url):
            # Calculate the next offset value
            current_offset = int(match.group(1))
            next_offset = current_offset + page_size
            return url.replace(match.group(1), str(next_offset))
        elif match.group(2):
            # Calculate the next page number
            current_page = int(match.group(2))
            next_page = current_page + 1
            return url.replace(match.group(2), str(next_page))
    return None

# Add tests to verify the changes
import unittest

class TestPagination(unittest.TestCase):
    def setUp(self):
        self.pagination = Pagination()

    def test_extract_page_number_offset(self):
        url = 'https://example.com/api?offset=10'
        self.assertEqual(self.pagination._extract_page_number(url), 10)

    def test_extract_page_number_start(self):
        url = 'https://example.com/api?start=20'
        self.assertEqual(self.pagination._extract_page_number(url), 20)

    def test_extract_page_number_page(self):
        url = 'https://example.com/api?page=3'
        self.assertEqual(self.pagination._extract_page_number(url), 3)

    def test_find_next_page_url_offset(self):
        url = 'https://example.com/api?offset=10'
        self.assertEqual(self.pagination.find_next_page_url(url, 5), 'https://example.com/api?offset=15')

    def test_find_next_page_url_start(self):
        url = 'https://example.com/api?start=20'
        self.assertEqual(self.pagination.find_next_page_url(url, 5), 'https://example.com/api?start=25')

    def test_find_next_page_url_page(self):
        url = 'https://example.com/api?page=3'
        self.assertEqual(self.pagination.find_next_page_url(url, 5), 'https://example.com/api?page=4')

if __name__ == '__main__':
    unittest.main()